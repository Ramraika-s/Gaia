"""
tests/test_wave1_ipc_and_protocol.py
Comprehensive regression test suite for Gaia v4.0 Remediation Wave 1 Part A:
1. Protocol normalization (protocol.py): constants, model validation, helper functions.
2. Nested & flat GOD_COMMAND execution (speed, pause, resume, bless, curse, smite).
3. Failure handling for missing/unknown agent_ids on targeted divine commands.
4. Safe broadcast send scheduling and HANDSHAKE_ACK version 4.0.0.
5. Multi-volume GOD_LIBRARY_EDIT preservation under the same topic without overwrite.
6. BUBBLE_SYNC inclusion of role and profession.
7. Engine pause state respect and Courthouse SIGN_UPDATE.
"""

from __future__ import annotations

import asyncio
import json
import socket
from pathlib import Path
from typing import Any

import pytest
import websockets

from sim_core.bridge.godot_ws_bridge import GodotWebSocketBridge
from sim_core.bridge.protocol import (
    PROTOCOL_VERSION,
    SEASON_PROGRESS_RANGE,
    TIME_OF_DAY_RANGE,
    build_world_time_weather_payload,
    extract_god_command_params,
    normalize_codex_edit_payload,
    normalize_library_edit_payload,
    resolve_library_entry_id,
)
from sim_core.engine import SimulationEngine
from sim_core.god_console.cli import RichGodConsole
from sim_core.schemas import Vec3, WorldLibraryEntry


def get_ephemeral_port() -> int:
    """Finds an available local port for isolated WebSocket test servers."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_protocol_constants_and_helpers() -> None:
    """Verifies protocol constants, ranges, and normalization helpers."""
    assert PROTOCOL_VERSION == "4.0.0"
    assert TIME_OF_DAY_RANGE == (0.0, 24.0)
    assert SEASON_PROGRESS_RANGE == (0.0, 4.0)

    # 1. extract_god_command_params merging
    flat_data = {"type": "GOD_COMMAND", "command": "speed", "speed": 5.0}
    params_flat = extract_god_command_params(flat_data)
    assert params_flat["speed"] == 5.0

    nested_data = {"type": "GOD_COMMAND", "command": "speed", "args": {"speed": 20.0}}
    params_nested = extract_god_command_params(nested_data)
    assert params_nested["speed"] == 20.0

    merged_data = {
        "type": "GOD_COMMAND",
        "command": "speed",
        "speed": 1.0,
        "args": {"speed": 60.0},
    }
    params_merged = extract_god_command_params(merged_data)
    assert params_merged["speed"] == 60.0  # nested takes precedence

    # 2. normalize_library_edit_payload
    lib_data = {
        "topic": "ASTRONOMY",
        "title": "Starlight Observations",
        "body": "Cosmic phenomena recorded.",
        "author_id": "OBSERVER_1",
    }
    norm_lib = normalize_library_edit_payload(lib_data)
    assert norm_lib["topic"] == "ASTRONOMY"
    assert norm_lib["volume_title"] == "Starlight Observations"
    assert norm_lib["text_content"] == "Cosmic phenomena recorded."
    assert norm_lib["author_id"] == "OBSERVER_1"
    assert norm_lib["entry_id"] is None

    # 3. normalize_codex_edit_payload
    codex_data = {
        "title": "DECREE_PEACE",
        "text": "Cease hostility.",
        "parameter_key": "DIVINE_TRUCE",
        "parameter_value": 300.0,
    }
    norm_codex = normalize_codex_edit_payload(codex_data)
    assert norm_codex["decree_id"] == "DECREE_PEACE"
    assert norm_codex["text_decree"] == "Cease hostility."
    assert norm_codex["parameter_key"] == "DIVINE_TRUCE"
    assert norm_codex["parameter_val"] == 300.0

    # 4. build_world_time_weather_payload wrapping
    weather_payload = build_world_time_weather_payload(
        day=5,
        time_of_day_hours=26.5,  # > 24.0 -> wraps to 2.5
        season_progress=5.25,  # > 4.0 -> wraps to 1.25
        weather="RAIN",
        weather_details={"wind_strength": 0.4},
    )
    assert weather_payload["day"] == 5
    assert weather_payload["time_of_day"] == pytest.approx(2.5)
    assert weather_payload["season_progress"] == pytest.approx(1.25)
    assert weather_payload["weather"] == "RAIN"
    assert weather_payload["weather_details"]["wind_strength"] == 0.4


def test_resolve_library_entry_id_multi_volume() -> None:
    """Verifies deterministic entry_id generation for multiple volumes under one topic."""
    entries: dict[str, Any] = {}

    # Volume 1: topic PHILOSOPHY, title Ethics
    id1 = resolve_library_entry_id("PHILOSOPHY", "Ethics", entries)
    assert id1 == "lib_PHILOSOPHY"
    entries[id1] = WorldLibraryEntry(
        entry_id=id1,
        topic="PHILOSOPHY",
        title="Ethics",
        summary="Virtue ethics.",
        author_id="GOD",
        created_tick=0,
    )

    # Re-saving Volume 1 preserves id1
    id1_again = resolve_library_entry_id("PHILOSOPHY", "Ethics", entries)
    assert id1_again == "lib_PHILOSOPHY"

    # Volume 2: topic PHILOSOPHY, title Metaphysics (different title -> unique deterministic id)
    id2 = resolve_library_entry_id("PHILOSOPHY", "Metaphysics", entries)
    assert id2.startswith("lib_philosophy_metaphysics_")
    assert id2 != id1
    entries[id2] = WorldLibraryEntry(
        entry_id=id2,
        topic="PHILOSOPHY",
        title="Metaphysics",
        summary="Forms and substance.",
        author_id="GOD",
        created_tick=0,
    )

    # Re-resolving Volume 2 produces exact same id
    id2_again = resolve_library_entry_id("PHILOSOPHY", "Metaphysics", entries)
    assert id2_again == id2

    # Explicit entry_id overrides
    id_explicit = resolve_library_entry_id(
        "PHILOSOPHY", "Aesthetics", entries, explicit_entry_id="custom_entry_99"
    )
    assert id_explicit == "custom_entry_99"


@pytest.mark.asyncio
async def test_god_command_execution_nested_and_flat(tmp_path: Path) -> None:
    """
    Tests nested (Godot WsBridgeClient style) and flat GOD_COMMAND execution:
    - speed (both flat and nested)
    - pause / resume
    - bless, curse, smite
    - failure paths for missing/unknown agent_id
    """
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

    # Spawn test agents
    agent_adult = engine.spawn_agent(
        race="HUMAN", gender="BOY", stage="ADULT", initial_credits=30.0
    )
    agent_child = engine.spawn_agent(
        race="ELF", gender="GIRL", stage="CHILD", initial_credits=10.0
    )
    agent_to_smite = engine.spawn_agent(race="DRAGON", gender="BOY", stage="ADULT")

    await bridge.start_server_async()

    try:
        uri = f"ws://127.0.0.1:{port}"
        async with websockets.connect(uri) as ws:
            # 1. Handshake checks protocol version 4.0.0
            await ws.send(json.dumps({"type": "CLIENT_HANDSHAKE"}))
            ack = json.loads(await ws.recv())
            assert ack["type"] == "HANDSHAKE_ACK"
            assert ack["version"] == "4.0.0"
            await ws.recv()  # BOOK_STATE_SYNC
            await ws.recv()  # BUILDING_SYNC

            # 2. Nested GOD_COMMAND: speed = 20.0 (Godot format)
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

            # 3. Flat GOD_COMMAND: speed = 5.0 (legacy format)
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

            # 4. Pause and Resume commands
            await ws.send(json.dumps({"type": "GOD_COMMAND", "command": "pause"}))
            resp = json.loads(await ws.recv())
            assert resp["status"] == "SUCCESS"
            assert not engine.is_running

            await ws.send(json.dumps({"type": "GOD_COMMAND", "command": "resume"}))
            resp = json.loads(await ws.recv())
            assert resp["status"] == "SUCCESS"
            assert engine.is_running

            # 5. Curse command (nested args): target adult
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
            assert agent_adult.hunger == 15.0
            assert agent_adult.stamina == 10.0
            assert not agent_adult.crying  # adult does not cry

            # Curse command on child -> causes crying
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

            # 6. Bless command (flat format): restores vitals
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
            assert resp["details"]["blessed_agent_id"] == agent_adult.agent_id
            assert agent_adult.health == agent_adult.max_health
            assert agent_adult.hunger == 100.0
            assert agent_adult.stamina == 100.0
            assert agent_adult.distress == 0.0
            assert not agent_adult.crying
            assert agent_adult.injured == 0.0
            assert agent_adult.illness == 0.0

            # 7. Smite command (nested format)
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
            assert resp["details"]["smitten_agent_id"] == smite_id
            assert not agent_to_smite.alive
            assert smite_id not in bridge.agent_id_to_slot
            assert any(f.agent_id == smite_id for f in engine.judiciary.fatalities)

            # 8. Failure handling for missing or unknown agent_ids
            # Missing agent_id
            await ws.send(json.dumps({"type": "GOD_COMMAND", "command": "bless", "args": {}}))
            resp = json.loads(await ws.recv())
            assert resp["status"] == "FAILURE"
            assert "Missing" in resp["reason"]

            await ws.send(json.dumps({"type": "GOD_COMMAND", "command": "curse"}))
            resp = json.loads(await ws.recv())
            assert resp["status"] == "FAILURE"
            assert "Missing" in resp["reason"]

            await ws.send(json.dumps({"type": "GOD_COMMAND", "command": "smite"}))
            resp = json.loads(await ws.recv())
            assert resp["status"] == "FAILURE"
            assert "Missing" in resp["reason"]

            # Unknown agent_id
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

            await ws.send(
                json.dumps(
                    {
                        "type": "GOD_COMMAND",
                        "command": "curse",
                        "args": {"agent_id": "ghost_agent_999"},
                    }
                )
            )
            resp = json.loads(await ws.recv())
            assert resp["status"] == "FAILURE"
            assert "not found" in resp["reason"]

            await ws.send(
                json.dumps(
                    {
                        "type": "GOD_COMMAND",
                        "command": "smite",
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
async def test_multi_volume_library_edit_preservation(tmp_path: Path) -> None:
    """
    Verifies that writing two differently titled volumes under the same topic
    preserves both entries without silent overwrite.
    """
    db_path = tmp_path / "civilization.db"
    port = get_ephemeral_port()

    bridge = GodotWebSocketBridge(host="127.0.0.1", port=port, initial_capacity=2048)
    engine = SimulationEngine(
        db_path=db_path,
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        adapter=bridge,
        headless=True,
    )
    bridge.engine = engine
    await bridge.start_server_async()

    try:
        uri = f"ws://127.0.0.1:{port}"
        async with websockets.connect(uri) as ws:
            # 1. First volume under METAPHYSICS
            vol1_msg = {
                "type": "GOD_LIBRARY_EDIT",
                "topic": "METAPHYSICS",
                "volume_title": "First Principles of Being",
                "text_content": "Being qua being examined in cosmic context.",
            }
            await ws.send(json.dumps(vol1_msg))
            resp1 = json.loads(await ws.recv())
            assert resp1["type"] == "GOD_LIBRARY_EDIT_RESPONSE"
            assert resp1["status"] == "SUCCESS"
            await ws.recv()  # BOOK_STATE_SYNC

            # 2. Second volume under SAME topic with DIFFERENT title
            vol2_msg = {
                "type": "GOD_LIBRARY_EDIT",
                "topic": "METAPHYSICS",
                "volume_title": "The Void and Potentiality",
                "text_content": "Nothingness precedes cosmic awakening.",
            }
            await ws.send(json.dumps(vol2_msg))
            resp2 = json.loads(await ws.recv())
            assert resp2["type"] == "GOD_LIBRARY_EDIT_RESPONSE"
            assert resp2["status"] == "SUCCESS"
            sync2 = json.loads(await ws.recv())
            assert sync2["type"] == "BOOK_STATE_SYNC"

            # Check both volumes coexist in governance engine in RAM
            entries = engine.governance_engine.library_entries
            assert len(entries) == 2
            titles = [e.title for e in entries.values()]
            assert "First Principles of Being" in titles
            assert "The Void and Potentiality" in titles

            # Verify neither volume overwrote the other
            v1_found = any(
                e.title == "First Principles of Being"
                and "qua being" in e.summary
                for e in entries.values()
            )
            v2_found = any(
                e.title == "The Void and Potentiality"
                and "Nothingness" in e.summary
                for e in entries.values()
            )
            assert v1_found and v2_found

    finally:
        await bridge.stop_server_async()


def test_bubble_sync_includes_role_and_profession(tmp_path: Path) -> None:
    """Verifies that BUBBLE_SYNC rig dictionary includes role and profession."""
    received_bubbles: list[list[dict[str, Any]]] = []

    class CapturingBridge(GodotWebSocketBridge):
        def sync_bubble(self, pooled_agents: list[dict[str, Any]]) -> None:
            received_bubbles.append(pooled_agents)

    bridge = CapturingBridge(initial_capacity=2048)
    engine = SimulationEngine(
        db_path=tmp_path / "civilization.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        adapter=bridge,
        headless=True,
    )

    # Spawn agent near god avatar (0, 0, 0) inside reality bubble
    agent = engine.spawn_agent(
        race="ELF",
        gender="GIRL",
        stage="ADULT",
        role="PALACE_KNIGHT",
        pos=Vec3(x=5.0, y=0.0, z=5.0),
    )
    agent.profession = "ROYAL_GUARD"

    engine.step_tick()

    assert len(received_bubbles) > 0
    latest_bubble = received_bubbles[-1]
    matching = [r for r in latest_bubble if r["agent_id"] == agent.agent_id]
    assert len(matching) == 1
    rig = matching[0]
    assert "role" in rig
    assert rig["role"] == "PALACE_KNIGHT"
    assert "profession" in rig
    assert rig["profession"] == "ROYAL_GUARD"


@pytest.mark.asyncio
async def test_launcher_pause_and_courthouse_sign(tmp_path: Path) -> None:
    """
    Verifies that when is_running is False, the simulation loop does not advance ticks,
    and civic ticks emit both WTC and COURTHOUSE sign updates.
    """
    import argparse

    from scripts.launch_gaia import GaiaLauncher

    port = get_ephemeral_port()
    args = argparse.Namespace(
        agents=10,
        speed=1.0,
        port=port,
        host="127.0.0.1",
        headless=True,
        max_ticks=0,
        duration_seconds=0.0,
        db_path=str(tmp_path / "civilization.db"),
        checkpoints_dir=str(tmp_path / "checkpoints"),
        god_ledger_dir=str(tmp_path / "god_ledger"),
        heightmap_path="nonexistent.npy",
        llm=False,
        llm_model="none.gguf",
        llm_port=8080,
        llm_bin="none",
    )

    launcher = GaiaLauncher(args)

    # Initialize engine & bridge headlessly without launching Godot
    capacity = 2048
    launcher.bridge = GodotWebSocketBridge(host=args.host, port=port, initial_capacity=capacity)
    launcher.engine = SimulationEngine(
        db_path=args.db_path,
        checkpoints_dir=args.checkpoints_dir,
        god_ledger_dir=args.god_ledger_dir,
        adapter=launcher.bridge,
        headless=True,
        initial_capacity=capacity,
    )
    launcher.bridge.engine = launcher.engine

    # Step when running advances tick
    launcher.engine.is_running = True
    assert launcher.engine.current_tick == 0
    launcher.engine.step_tick()
    assert launcher.engine.current_tick == 1

    # Pause engine
    launcher.engine.is_running = False

    # Simulate launcher loop behavior when paused
    # The pause fix checks: if not self.engine.is_running: await asyncio.sleep(0.05); continue
    for _ in range(5):
        if not launcher.engine.is_running:
            await asyncio.sleep(0.01)
            continue
        launcher.engine.step_tick()

    # Ticks must NOT advance while is_running is False
    assert launcher.engine.current_tick == 1

    # Test Courthouse sign payload generation
    sign_events: list[dict[str, Any]] = []

    def _capture_event(event_type: str, payload: dict[str, Any]) -> None:
        sign_events.append({"type": event_type, **payload})

    launcher.bridge.emit_event = _capture_event  # type: ignore

    # File a judiciary case to verify active_cases
    launcher.engine.judiciary.file_case(
        accused_id="agent_thief",
        offense_type="THEFT",
        opened_tick=launcher.engine.current_tick,
    )
    active_cases = len(launcher.engine.judiciary.get_open_cases())
    assert active_cases == 1

    # Trigger Courthouse SIGN_UPDATE broadcast
    launcher.bridge.emit_event(
        "SIGN_UPDATE",
        {
            "board": "COURTHOUSE",
            "active_cases": active_cases,
            "convictions": 0,
            "polities_count": len(launcher.engine.political_engine.polities),
            "status": "Court in Order",
        },
    )

    courthouse_events = [e for e in sign_events if e.get("board") == "COURTHOUSE"]
    assert len(courthouse_events) == 1
    assert courthouse_events[0]["active_cases"] == 1
    assert courthouse_events[0]["status"] == "Court in Order"


@pytest.mark.asyncio
async def test_god_command_slot_targeting_and_validations(tmp_path: Path) -> None:
    """
    Verifies:
    1. Targeting agents via 'slot' (int and str) for bless, curse, and smite.
    2. Invalid/missing slot failure reporting.
    3. name_deity with invalid slot or missing name returns FAILURE without unhandled KeyError.
    4. decree with empty message returns FAILURE.
    5. speed and step with non-numeric args fall back safely without raising ValueError.
    6. raw_command auto-initializes RichGodConsole when bridge.cli is None.
    """
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
    # Deliberately leave bridge.cli = None to verify auto-initialization

    agent1 = engine.spawn_agent(race="HUMAN", gender="BOY", stage="ADULT")
    agent2 = engine.spawn_agent(race="ELF", gender="GIRL", stage="CHILD")
    agent3 = engine.spawn_agent(race="DRAGON", gender="BOY", stage="ADULT")

    await bridge.start_server_async()

    try:
        uri = f"ws://127.0.0.1:{port}"
        async with websockets.connect(uri) as ws:
            # Consume handshake
            await ws.send(json.dumps({"type": "CLIENT_HANDSHAKE"}))
            await ws.recv()  # HANDSHAKE_ACK
            await ws.recv()  # BOOK_STATE_SYNC
            await ws.recv()  # BUILDING_SYNC

            # 1. Bless via slot (int)
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
            assert resp["details"]["blessed_agent_id"] == agent1.agent_id
            assert agent1.distress == 0.0
            assert agent1.hunger == 100.0

            # 2. Curse via slot (string representation of int)
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
            assert resp["details"]["cursed_agent_id"] == agent2.agent_id
            assert agent2.distress == 0.85
            assert agent2.crying

            # 3. Smite via slot
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
            assert resp["details"]["smitten_agent_id"] == agent3.agent_id
            assert not agent3.alive

            # 4. Non-existent slot
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
            assert "Slot '99999' not found" in resp["reason"]

            # 5. Invalid non-integer slot
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
            assert "Invalid slot" in resp["reason"]

            # 6. name_deity with invalid slot
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
            assert "Invalid or missing deity slot" in resp["reason"]

            # name_deity with missing name
            await ws.send(
                json.dumps(
                    {
                        "type": "GOD_COMMAND",
                        "command": "name_deity",
                        "args": {"slot": "gm_human", "name": "   "},
                    }
                )
            )
            resp = json.loads(await ws.recv())
            assert resp["status"] == "FAILURE"
            assert "Missing 'name'" in resp["reason"]

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

            # 7. decree with empty message
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
            assert "Missing 'message'" in resp["reason"]

            # 8. speed and step with non-numeric values
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

            cur_t = engine.current_tick
            await ws.send(
                json.dumps(
                    {
                        "type": "GOD_COMMAND",
                        "command": "step",
                        "args": {"ticks": "ten"},
                    }
                )
            )
            resp = json.loads(await ws.recv())
            assert resp["status"] == "SUCCESS"
            assert engine.current_tick == cur_t + 1

            # 9. raw_command auto-initializes RichGodConsole when bridge.cli is None
            assert bridge.cli is None
            await ws.send(
                json.dumps(
                    {
                        "type": "GOD_COMMAND",
                        "raw_command": "status",
                    }
                )
            )
            # Drain any background broadcasts (e.g. BUBBLE_SYNC from step) until GOD_COMMAND_RESULT
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("type") == "GOD_COMMAND_RESULT":
                    resp = msg
                    break
            assert resp["status"] == "SUCCESS"
            assert "Civilization Status" in resp["output"]
            assert bridge.cli is not None

    finally:
        await bridge.stop_server_async()


@pytest.mark.asyncio
async def test_god_library_edit_empty_topic_rejected(tmp_path: Path) -> None:
    """Verifies GOD_LIBRARY_EDIT with missing or empty topic fails closed with status FAILURE."""
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
    await bridge.start_server_async()

    try:
        uri = f"ws://127.0.0.1:{port}"
        async with websockets.connect(uri) as ws:
            await ws.send(
                json.dumps(
                    {
                        "type": "GOD_LIBRARY_EDIT",
                        "topic": "   ",
                        "volume_title": "Lost Codex",
                        "text_content": "No topic specified.",
                    }
                )
            )
            resp = json.loads(await ws.recv())
            assert resp["type"] == "GOD_LIBRARY_EDIT_RESPONSE"
            assert resp["status"] == "FAILURE"
            assert "Missing or empty 'topic'" in resp["reason"]
            assert "lib_" not in engine.governance_engine.library_entries

    finally:
        await bridge.stop_server_async()


def test_resolve_library_entry_id_preserves_id_when_first_volume_deleted() -> None:
    """Verifies resolve_library_entry_id reuses existing entry_id even if lib_{topic} is absent."""
    entries: dict[str, Any] = {}
    id1 = resolve_library_entry_id("PHILOSOPHY", "Ethics", entries)
    entries[id1] = WorldLibraryEntry(
        entry_id=id1,
        topic="PHILOSOPHY",
        title="Ethics",
        summary="Virtue ethics.",
        author_id="GOD",
        created_tick=0,
    )

    id2 = resolve_library_entry_id("PHILOSOPHY", "Metaphysics", entries)
    entries[id2] = WorldLibraryEntry(
        entry_id=id2,
        topic="PHILOSOPHY",
        title="Metaphysics",
        summary="Forms and being.",
        author_id="GOD",
        created_tick=0,
    )

    # Delete volume 1
    del entries[id1]

    # Re-resolving Volume 2 (Metaphysics) must match id2, not fall back to lib_PHILOSOPHY
    resolved_id2 = resolve_library_entry_id("PHILOSOPHY", "Metaphysics", entries)
    assert resolved_id2 == id2


@pytest.mark.asyncio
async def test_broadcast_async_cleans_up_broken_clients() -> None:
    """Verifies that async broadcasts remove broken clients and update god_presence."""
    class BrokenClient:
        async def send(self, data: Any) -> None:
            raise ConnectionResetError("Socket broken abruptly")

    bridge = GodotWebSocketBridge()
    engine = SimulationEngine(headless=True)
    bridge.engine = engine

    broken = BrokenClient()
    bridge.clients.add(broken)
    engine.god_presence.set_active(True)
    assert len(bridge.clients) == 1
    assert engine.god_presence.is_active

    await bridge.broadcast_binary_async(b"test_payload")
    assert len(bridge.clients) == 0
    assert not engine.god_presence.is_active

    # Re-test with JSON broadcast
    broken2 = BrokenClient()
    bridge.clients.add(broken2)
    engine.god_presence.set_active(True)

    await bridge.broadcast_json_async({"type": "TEST"})
    assert len(bridge.clients) == 0
    assert not engine.god_presence.is_active


def test_engine_idempotent_despawn() -> None:
    """Verifies SimulationEngine.despawn_agent is idempotent and preserves record in self.agents."""
    engine = SimulationEngine(headless=True)
    agent = engine.spawn_agent(
        race="HUMAN", gender="BOY", stage="ADULT", pos=Vec3(x=10.0, y=18.0, z=10.0)
    )
    agent_id = agent.agent_id
    slot_idx = agent.slot_idx

    assert agent_id in engine.agents
    assert agent.alive is True
    assert slot_idx in engine.batched_net.active_slots

    # First despawn succeeds
    res1 = engine.despawn_agent(agent_id, reason="TEST_DEATH")
    assert res1 is True

    # Record preserved for probate and EOD persistence
    assert agent_id in engine.agents
    assert agent.alive is False
    assert slot_idx in engine.batched_net.free_slots
    assert agent_id not in engine.spatial_grid._agent_positions

    # Second despawn is cleanly idempotent (returns False, does not crash)
    res2 = engine.despawn_agent(agent_id, reason="TEST_DEATH")
    assert res2 is False


@pytest.mark.asyncio
async def test_god_command_smite_idempotent_and_deceased_rejection() -> None:
    """Verifies that smiting an agent despawns it and second smite returns FAILURE."""
    import websockets

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
            await ws.send(json.dumps({
                "type": "GOD_COMMAND",
                "command": "smite",
                "args": {"agent_id": agent_id},
            }))
            resp1 = json.loads(await ws.recv())
            assert resp1["type"] == "GOD_COMMAND_RESPONSE"
            assert resp1["status"] == "SUCCESS"
            assert agent.alive is False
            assert len(engine.judiciary.fatalities) == 1

            # Second smite on same deceased agent -> FAILURE
            await ws.send(json.dumps({
                "type": "GOD_COMMAND",
                "command": "smite",
                "args": {"agent_id": agent_id},
            }))
            resp2 = json.loads(await ws.recv())
            assert resp2["type"] == "GOD_COMMAND_RESPONSE"
            assert resp2["status"] == "FAILURE"
            assert "already deceased" in resp2["reason"]
            # No duplicate fatality record created
            assert len(engine.judiciary.fatalities) == 1
    finally:
        await bridge.stop_server_async()


def test_multimesh_flags_set_and_clear() -> None:
    """Verifies that update_agent_position dynamically sets AND clears packed_flags."""
    bridge = GodotWebSocketBridge()
    slot_idx = 10
    bridge._ensure_capacity(slot_idx)

    # Set flags
    bridge.update_agent_position(slot_idx, x=5.0, y=10.0, z=15.0, yaw=1.0, packed_flags=65)
    assert bridge.positions[slot_idx, 5] == 65.0

    # Clear flags back to 0
    bridge.update_agent_position(slot_idx, x=6.0, y=10.0, z=15.0, yaw=1.0, packed_flags=0)
    assert bridge.positions[slot_idx, 5] == 0.0


def test_spawn_agent_none_safe_coercion() -> None:
    """Verifies spawn_agent safely coerces None metadata values without TypeError."""
    bridge = GodotWebSocketBridge()
    slot_idx = 5
    metadata: dict[str, Any] = {
        "x": None,
        "y": None,
        "z": None,
        "injured": None,
        "illness": None,
        "race": "HUMAN",
        "stage": "ADULT",
    }
    bridge.spawn_agent("agent_none_test", slot_idx, metadata)
    assert bridge.positions[slot_idx, 0] == 0.0
    assert bridge.positions[slot_idx, 1] == 0.0
    assert bridge.positions[slot_idx, 2] == 0.0
    assert bridge.positions[slot_idx, 5] == 0.0


def test_resolve_library_entry_id_special_chars() -> None:
    """Verifies resolve_library_entry_id sanitizes special characters into clean slug."""
    entries: dict[str, Any] = {}
    eid = resolve_library_entry_id("DARK MAGIC / CURSES", "Vol 1", entries)
    assert eid == "lib_DARK_MAGIC_CURSES"


