"""
tests/bridge/test_god_console_cli.py
Tests the Rich God Console interactive CLI, god commands, presence tracking, and DuckDB analytics.
"""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest
import websockets

from sim_core.bridge.godot_ws_bridge import GodotWebSocketBridge
from sim_core.engine import SimulationEngine
from sim_core.god_console.cli import RichGodConsole


def get_ephemeral_port() -> int:
    """Finds an available local port for isolated WebSocket test servers."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.asyncio
async def test_god_presence_tracker_active_vs_away(tmp_path: Path) -> None:
    """
    Verifies that when God is AWAY, messages stay strictly in RAM and flush to
    data/god_ledger/day_XXXXX.md at end-of-day; when ACTIVE, messages stream immediately.
    """
    ledger_dir = tmp_path / "god_ledger"
    engine = SimulationEngine(
        db_path=tmp_path / "civilization.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=ledger_dir,
        headless=True,
    )

    assert not engine.god_presence.is_active
    away_entry = engine.ledger_pipeline.record_deity_message(
        entry_id="msg_away_01",
        day=engine.current_day,
        tick=engine.current_tick,
        category="WORLD_GODDESS_SUMMARY",
        deity_slot="world_goddess",
        speaker_name="World Goddess",
        message="The stars remain in alignment while you are away.",
    )
    assert not away_entry.delivered_realtime
    assert len(engine.ledger_pipeline.buffer) == 1

    engine.commit_end_of_day()
    day1_file = ledger_dir / "day_00001.md"
    assert day1_file.exists()
    content = day1_file.read_text(encoding="utf-8")
    assert "The stars remain in alignment while you are away." in content
    assert (ledger_dir / "latest.md").exists()

    port = get_ephemeral_port()
    bridge = GodotWebSocketBridge(host="127.0.0.1", port=port, engine=engine)
    engine.adapter = bridge
    await bridge.start_server_async()

    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send(json.dumps({"type": "GOD_STATE", "x": 0.0, "y": 0.0, "z": 0.0}))
            resp = json.loads(await ws.recv())
            assert resp["type"] == "GOD_STATE_ACK"
            assert resp["status"] == "ACTIVE"
            assert engine.god_presence.is_active

            active_entry = engine.ledger_pipeline.record_deity_message(
                entry_id="msg_active_01",
                day=engine.current_day,
                tick=engine.current_tick,
                category="GOD_MOTHER_REPORT",
                deity_slot="gm_human",
                speaker_name="Human God-Mother",
                message="Mortals rejoice in your immediate divine presence!",
            )
            assert active_entry.delivered_realtime

            bridge.emit_event(
                "DIVINE_HUD_MESSAGE",
                {
                    "entry_id": active_entry.entry_id,
                    "speaker_name": active_entry.speaker_name,
                    "message": active_entry.message,
                },
            )
            event_raw = await ws.recv()
            event_data = json.loads(event_raw)
            assert event_data["type"] == "DIVINE_HUD_MESSAGE"
            assert "rejoice in your immediate divine presence" in event_data["message"]
    finally:
        await bridge.stop_server_async()
        assert not engine.god_presence.is_active


def test_speed_control(tmp_path: Path) -> None:
    """Verifies that simulation speed accelerates cleanly without desyncing calendar day."""
    engine = SimulationEngine(
        db_path=tmp_path / "civilization.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        headless=True,
    )

    assert engine.speed == 1.0
    initial_season = engine.current_season

    engine.set_speed(20.0)
    assert engine.speed == 20.0

    for _ in range(120):
        engine.step_tick()

    assert engine.current_tick == 120
    assert engine.current_season == initial_season

    engine.set_speed(1.0)
    assert engine.speed == 1.0


@pytest.mark.slow
def test_rich_cli_and_duckdb_read_only_analytics(tmp_path: Path) -> None:
    """Verifies core Rich God Console inspect/intervene commands and DuckDB read-only analytics."""
    db_path = tmp_path / "civilization.db"
    engine = SimulationEngine(
        db_path=db_path,
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        headless=True,
    )

    for race in ("HUMAN", "ELF", "DRAGON", "BEASTHUMAN"):
        engine.spawn_agent(race=race, gender="GIRL", stage="ADULT", initial_credits=50.0)

    console = RichGodConsole(engine=engine)

    # Status
    status_out = console.execute_command("status")
    assert "Living Agents" in status_out
    assert "Day 1" in status_out

    # Pop
    pop_out = console.execute_command("pop")
    assert "HUMAN" in pop_out
    assert "ELF" in pop_out
    assert "DRAGON" in pop_out
    assert "BEASTHUMAN" in pop_out

    # Intervene: name_deity
    name_out = console.execute_command('name_deity gm_human "Aurelia"')
    assert "Aurelia" in name_out
    assert engine.divine_hierarchy.entities["gm_human"].bestowed_name == "Aurelia"

    # Intervene: speed
    speed_out = console.execute_command("speed 20x")
    assert "20.0x" in speed_out
    assert engine.speed == 20.0

    # Intervene: codex write
    decree_out = console.execute_command('codex write decree_01 "Mortals harvest in peace."')
    assert "decree_01" in decree_out

    # Intervene: codex approve
    ok, _, prop = engine.governance_engine.submit_parameter_override_proposal(
        title="Max Oracles",
        text="Grant each race a 4th Oracle slot.",
        parameter_key="MAX_ORACLES",
        parameter_value=4.0,
        proposer_slot="world_goddess",
        co_sponsors=[],
        current_tick=engine.current_tick,
    )
    assert ok and prop is not None
    approve_out = console.execute_command(f"codex approve {prop.proposal_id}")
    assert "SUCCESS" in approve_out
    assert engine.governance_engine.live_engine_overrides["MAX_ORACLES"] == 4.0

    # Intervene: save
    save_out = console.execute_command("save")
    assert "Atomic save committed successfully" in save_out
    assert engine.current_day == 1

    # DuckDB Analytics
    analytics_out = console.execute_command("analytics demographics")
    assert "DuckDB Analytics: DEMOGRAPHICS" in analytics_out
    assert "HUMAN" in analytics_out

    # Step and commit again cleanly without lock issues
    engine.step_tick()
    save_out2 = console.execute_command("save")
    assert "Atomic save committed successfully" in save_out2
    assert engine.current_day == 1


@pytest.mark.asyncio
async def test_god_command_execution_nested_and_flat(tmp_path: Path) -> None:
    """Tests nested and flat GOD_COMMAND execution: speed, pause, bless, curse, smite."""
    db_path = tmp_path / "civilization.db"
    checkpoints_dir = tmp_path / "checkpoints"
    god_ledger_dir = tmp_path / "god_ledger"
    port = get_ephemeral_port()

    bridge = GodotWebSocketBridge(host="127.0.0.1", port=port, initial_capacity=2048)
    engine = SimulationEngine(
        db_path=db_path,
        checkpoints_dir=checkpoints_dir,
        god_ledger_dir=god_ledger_dir,
        adapter=bridge,
        headless=True,
        initial_capacity=2048,
    )
    bridge.engine = engine
    cli = RichGodConsole(engine=engine)
    bridge.cli = cli

    agent_adult = engine.spawn_agent(
        race="HUMAN", gender="BOY", stage="ADULT", initial_credits=30.0
    )
    agent_child = engine.spawn_agent(race="ELF", gender="GIRL", stage="CHILD", initial_credits=10.0)
    agent_to_smite = engine.spawn_agent(race="DRAGON", gender="BOY", stage="ADULT")

    await bridge.start_server_async()

    try:
        uri = f"ws://127.0.0.1:{port}"
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({"type": "CLIENT_HANDSHAKE"}))
            ack = json.loads(await ws.recv())
            assert ack["type"] == "HANDSHAKE_ACK"
            assert ack["version"] == "4.0.0"
            await ws.recv()  # BOOK_STATE_SYNC
            await ws.recv()  # BUILDING_SYNC

            # Nested speed
            await ws.send(
                json.dumps(
                    {
                        "type": "GOD_COMMAND",
                        "command": "speed",
                        "args": {"speed": 20.0},
                    }
                )
            )
            resp = json.loads(await ws.recv())
            assert resp["type"] == "GOD_COMMAND_RESPONSE"
            assert resp["status"] == "SUCCESS"
            assert resp["details"]["speed"] == 20.0
            assert engine.speed == 20.0

            # Flat speed
            await ws.send(
                json.dumps(
                    {
                        "type": "GOD_COMMAND",
                        "command": "speed",
                        "speed": 5.0,
                    }
                )
            )
            resp = json.loads(await ws.recv())
            assert resp["type"] == "GOD_COMMAND_RESPONSE"
            assert resp["status"] == "SUCCESS"
            assert resp["details"]["speed"] == 5.0
            assert engine.speed == 5.0

            # Pause & resume
            await ws.send(json.dumps({"type": "GOD_COMMAND", "command": "pause"}))
            resp = json.loads(await ws.recv())
            assert resp["status"] == "SUCCESS"
            assert not engine.is_running

            await ws.send(json.dumps({"type": "GOD_COMMAND", "command": "resume"}))
            resp = json.loads(await ws.recv())
            assert resp["status"] == "SUCCESS"
            assert engine.is_running

            # Curse adult
            await ws.send(
                json.dumps(
                    {
                        "type": "GOD_COMMAND",
                        "command": "curse",
                        "args": {"agent_id": agent_adult.agent_id},
                    }
                )
            )
            resp = json.loads(await ws.recv())
            assert resp["status"] == "SUCCESS"
            assert resp["details"]["cursed_agent_id"] == agent_adult.agent_id
            assert agent_adult.distress == 0.85
            assert not agent_adult.crying

            # Curse child -> crying
            await ws.send(
                json.dumps(
                    {
                        "type": "GOD_COMMAND",
                        "command": "curse",
                        "args": {"agent_id": agent_child.agent_id},
                    }
                )
            )
            resp = json.loads(await ws.recv())
            assert resp["status"] == "SUCCESS"
            assert agent_child.crying

            # Bless adult
            agent_adult.health = 10.0
            agent_adult.injured = 0.5
            agent_adult.illness = 0.5
            await ws.send(
                json.dumps(
                    {
                        "type": "GOD_COMMAND",
                        "command": "bless",
                        "agent_id": agent_adult.agent_id,
                    }
                )
            )
            resp = json.loads(await ws.recv())
            assert resp["status"] == "SUCCESS"
            assert agent_adult.health == agent_adult.max_health
            assert agent_adult.injured == 0.0

            # Smite
            smite_id = agent_to_smite.agent_id
            await ws.send(
                json.dumps(
                    {
                        "type": "GOD_COMMAND",
                        "command": "smite",
                        "args": {"agent_id": smite_id},
                    }
                )
            )
            resp = json.loads(await ws.recv())
            assert resp["status"] == "SUCCESS"
            assert not agent_to_smite.alive
            assert smite_id not in bridge.agent_id_to_slot
            assert any(f.agent_id == smite_id for f in engine.judiciary.fatalities)

            # Failure paths
            await ws.send(json.dumps({"type": "GOD_COMMAND", "command": "bless", "args": {}}))
            resp = json.loads(await ws.recv())
            assert resp["status"] == "FAILURE"

            await ws.send(
                json.dumps(
                    {
                        "type": "GOD_COMMAND",
                        "command": "bless",
                        "args": {"agent_id": "ghost_agent_999"},
                    }
                )
            )
            resp = json.loads(await ws.recv())
            assert resp["status"] == "FAILURE"
            assert "not found" in resp["reason"]
    finally:
        await bridge.stop_server_async()


@pytest.mark.asyncio
async def test_god_command_slot_targeting_and_validations(tmp_path: Path) -> None:
    """Verifies targeting agents via slot, invalid slots, and non-numeric fallbacks."""
    port = get_ephemeral_port()
    bridge = GodotWebSocketBridge(host="127.0.0.1", port=port, initial_capacity=2048)
    engine = SimulationEngine(
        db_path=tmp_path / "civilization.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        adapter=bridge,
        headless=True,
    )
    bridge.engine = engine

    agent1 = engine.spawn_agent(race="HUMAN", gender="BOY", stage="ADULT")
    agent2 = engine.spawn_agent(race="ELF", gender="GIRL", stage="CHILD")
    agent3 = engine.spawn_agent(race="DRAGON", gender="BOY", stage="ADULT")

    await bridge.start_server_async()

    try:
        uri = f"ws://127.0.0.1:{port}"
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({"type": "CLIENT_HANDSHAKE"}))
            await ws.recv()  # HANDSHAKE_ACK
            await ws.recv()  # BOOK_STATE_SYNC
            await ws.recv()  # BUILDING_SYNC

            # Bless via slot (int)
            agent1.distress = 0.9
            agent1.hunger = 20.0
            await ws.send(
                json.dumps(
                    {
                        "type": "GOD_COMMAND",
                        "command": "bless",
                        "args": {"slot": agent1.slot_idx},
                    }
                )
            )
            resp = json.loads(await ws.recv())
            assert resp["status"] == "SUCCESS"
            assert agent1.distress == 0.0

            # Curse via slot (str)
            await ws.send(
                json.dumps(
                    {
                        "type": "GOD_COMMAND",
                        "command": "curse",
                        "args": {"slot": str(agent2.slot_idx)},
                    }
                )
            )
            resp = json.loads(await ws.recv())
            assert resp["status"] == "SUCCESS"
            assert agent2.crying

            # Smite via slot
            await ws.send(
                json.dumps(
                    {
                        "type": "GOD_COMMAND",
                        "command": "smite",
                        "args": {"slot": agent3.slot_idx},
                    }
                )
            )
            resp = json.loads(await ws.recv())
            assert resp["status"] == "SUCCESS"
            assert not agent3.alive

            # Non-existent slot
            await ws.send(
                json.dumps(
                    {
                        "type": "GOD_COMMAND",
                        "command": "bless",
                        "args": {"slot": 99999},
                    }
                )
            )
            resp = json.loads(await ws.recv())
            assert resp["status"] == "FAILURE"

            # Invalid non-integer slot
            await ws.send(
                json.dumps(
                    {
                        "type": "GOD_COMMAND",
                        "command": "bless",
                        "args": {"slot": "not_an_int"},
                    }
                )
            )
            resp = json.loads(await ws.recv())
            assert resp["status"] == "FAILURE"

            # name_deity with invalid slot
            await ws.send(
                json.dumps(
                    {
                        "type": "GOD_COMMAND",
                        "command": "name_deity",
                        "args": {"slot": "bogus_god", "name": "FakeName"},
                    }
                )
            )
            resp = json.loads(await ws.recv())
            assert resp["status"] == "FAILURE"

            # name_deity valid
            await ws.send(
                json.dumps(
                    {
                        "type": "GOD_COMMAND",
                        "command": "name_deity",
                        "args": {"slot": "gm_human", "name": "Aurelia"},
                    }
                )
            )
            resp = json.loads(await ws.recv())
            assert resp["status"] == "SUCCESS"
            assert engine.divine_hierarchy.entities["gm_human"].bestowed_name == "Aurelia"

            # Decree with empty message
            await ws.send(
                json.dumps(
                    {
                        "type": "GOD_COMMAND",
                        "command": "decree",
                        "args": {"message": "   "},
                    }
                )
            )
            resp = json.loads(await ws.recv())
            assert resp["status"] == "FAILURE"

            # Speed with non-numeric
            await ws.send(
                json.dumps(
                    {
                        "type": "GOD_COMMAND",
                        "command": "speed",
                        "args": {"speed": "ultra_fast"},
                    }
                )
            )
            resp = json.loads(await ws.recv())
            assert resp["status"] == "SUCCESS"
            assert resp["details"]["speed"] == 1.0

            # raw_command auto-initializes RichGodConsole when bridge.cli is None
            assert bridge.cli is None
            await ws.send(
                json.dumps(
                    {
                        "type": "GOD_COMMAND",
                        "raw_command": "status",
                    }
                )
            )
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("type") == "GOD_COMMAND_RESULT":
                    resp = msg
                    break
            assert resp["status"] == "SUCCESS"
            assert bridge.cli is not None
    finally:
        await bridge.stop_server_async()


@pytest.mark.asyncio
async def test_god_command_smite_idempotent_and_deceased_rejection() -> None:
    """Verifies that smiting an agent despawns it and second smite returns FAILURE."""
    port = get_ephemeral_port()
    bridge = GodotWebSocketBridge(port=port)
    engine = SimulationEngine(headless=True)
    bridge.engine = engine
    agent = engine.spawn_agent(race="HUMAN", gender="BOY", stage="ADULT")
    agent_id = agent.agent_id

    await bridge.start_server_async()
    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            # First smite -> SUCCESS
            await ws.send(
                json.dumps(
                    {
                        "type": "GOD_COMMAND",
                        "command": "smite",
                        "args": {"agent_id": agent_id},
                    }
                )
            )
            resp1 = json.loads(await ws.recv())
            assert resp1["type"] == "GOD_COMMAND_RESPONSE"
            assert resp1["status"] == "SUCCESS"
            assert agent.alive is False
            assert len(engine.judiciary.fatalities) == 1

            # Second smite on same deceased agent -> FAILURE
            await ws.send(
                json.dumps(
                    {
                        "type": "GOD_COMMAND",
                        "command": "smite",
                        "args": {"agent_id": agent_id},
                    }
                )
            )
            resp2 = json.loads(await ws.recv())
            assert resp2["type"] == "GOD_COMMAND_RESPONSE"
            assert resp2["status"] == "FAILURE"
            assert "already deceased" in resp2["reason"]
            assert len(engine.judiciary.fatalities) == 1
    finally:
        await bridge.stop_server_async()


def test_console_codex_write_type_parsing(tmp_path: Path) -> None:
    """Verifies typed parameter parsing in codex write command."""
    db_path = tmp_path / "civ_codex.db"
    checkpoints_dir = tmp_path / "checkpoints"
    god_ledger_dir = tmp_path / "god_ledger"

    engine = SimulationEngine(
        db_path=db_path,
        checkpoints_dir=checkpoints_dir,
        god_ledger_dir=god_ledger_dir,
        headless=True,
    )
    console = RichGodConsole(engine=engine)

    # Bool true
    out1 = console.execute_command(
        "codex write DEC_TRUE 'Decree True' NON_AGGRESSION_COVENANT true"
    )
    assert "SUCCESS" in out1
    assert engine.governance_engine.live_engine_overrides["NON_AGGRESSION_COVENANT"] is True

    # Bool false
    out2 = console.execute_command(
        "codex write DEC_FALSE 'Decree False' NON_AGGRESSION_COVENANT false"
    )
    assert "SUCCESS" in out2
    assert engine.governance_engine.live_engine_overrides["NON_AGGRESSION_COVENANT"] is False

    # Integer
    out3 = console.execute_command("codex write DEC_INT 'Decree Int' MAX_ORACLES 7")
    assert "SUCCESS" in out3
    assert engine.governance_engine.live_engine_overrides["MAX_ORACLES"] == 7

    # Float
    out4 = console.execute_command("codex write DEC_FLOAT 'Decree Float' DIVINE_TRUCE_HOURS 72.5")
    assert "SUCCESS" in out4
    assert engine.governance_engine.live_engine_overrides["DIVINE_TRUCE_HOURS"] == 72.5

    # String
    out5 = console.execute_command("codex write DEC_STR 'Decree Str' TRUCE_REASON 'sacred_accord'")
    assert "SUCCESS" in out5
    assert engine.governance_engine.live_engine_overrides["TRUCE_REASON"] == "sacred_accord"

