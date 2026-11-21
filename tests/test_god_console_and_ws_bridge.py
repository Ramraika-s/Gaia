"""
tests/test_god_console_and_ws_bridge.py
Phase 4 Acceptance Tests:
1. GodPresenceTracker (Active vs. Away) message buffering and live streaming.
2. 10,000-Agent Binary Stream Benchmark (< 2.0 ms serialization latency, 240,000 bytes).
3. Zero Direct SQLite writes + Live Two-Book Edits (GOD_LIBRARY_EDIT, GOD_CODEX_APPROVE).
4. Speed Control (1x -> 20x -> 1x) without desyncing clock/season counters.
5. Rich God Console CLI commands & DuckDB read-only analytics execution.
"""

from __future__ import annotations

import json
import socket
import sqlite3
import time
from pathlib import Path

import numpy as np
import pytest
import websockets

from sim_core.bridge.godot_ws_bridge import (
    FLAG_CRYING,
    FLAG_IS_ORACLE,
    GodotWebSocketBridge,
)
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

    # 1. Initially AWAY
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

    # End of day commit should compile and flush the buffered messages to markdown
    engine.commit_end_of_day()
    day1_file = ledger_dir / "day_00001.md"
    assert day1_file.exists()
    content = day1_file.read_text(encoding="utf-8")
    assert "The stars remain in alignment while you are away." in content
    assert (ledger_dir / "latest.md").exists()

    # 2. God becomes ACTIVE
    port = get_ephemeral_port()
    bridge = GodotWebSocketBridge(host="127.0.0.1", port=port, engine=engine)
    engine.adapter = bridge
    await bridge.start_server_async()

    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            # Client connects and sets presence
            await ws.send(json.dumps({"type": "GOD_STATE", "x": 0.0, "y": 0.0, "z": 0.0}))
            resp = json.loads(await ws.recv())
            assert resp["type"] == "GOD_STATE_ACK"
            assert resp["status"] == "ACTIVE"
            assert engine.god_presence.is_active

            # Record message while active
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

            # Bridge emits live DIVINE_HUD_MESSAGE event
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
        # Disconnecting resets God presence back to AWAY
        assert not engine.god_presence.is_active


@pytest.mark.asyncio
async def test_10000_agent_binary_stream_benchmark() -> None:
    """
    Verifies that a real local WebSocket client receives binary PackedFloat32Array
    frames for 10,000 agents (240,000 bytes/frame) with serialization latency under 2.0 ms
    and exact coordinate round-trip verification.
    """
    port = get_ephemeral_port()
    bridge = GodotWebSocketBridge(host="127.0.0.1", port=port, initial_capacity=10240)
    await bridge.start_server_async()

    # Pre-generate 10,000 synthetic agent positions and flags
    n_agents = 10000
    expected_data = np.zeros((n_agents, 6), dtype="<f4")
    # Coordinates: x, y, z
    expected_data[:, 0] = np.linspace(-4000.0, 4000.0, n_agents, dtype="<f4")
    expected_data[:, 1] = np.linspace(10.0, 500.0, n_agents, dtype="<f4")
    expected_data[:, 2] = np.linspace(-4000.0, 4000.0, n_agents, dtype="<f4")
    # Race float: 0.0, 1.0, 2.0, 3.0
    expected_data[:, 3] = (np.arange(n_agents) % 4).astype("<f4")
    # Stage float: 0.0, 1.0, 2.0, 3.0
    expected_data[:, 4] = (np.arange(n_agents) % 4).astype("<f4")
    # Packed flags float
    expected_data[:, 5] = ((np.arange(n_agents) % 2) * (FLAG_CRYING | FLAG_IS_ORACLE)).astype("<f4")

    # Populate bridge buffer
    bridge._ensure_capacity(n_agents)
    bridge.positions[:n_agents] = expected_data
    bridge.active_mask[:n_agents] = True

    # Benchmark serialization latency
    timings = []
    for _ in range(10):
        t0 = time.perf_counter()
        binary_payload = bridge.pack_binary_frame()
        t1 = time.perf_counter()
        timings.append((t1 - t0) * 1000.0)

    avg_latency_ms = sum(timings) / len(timings)
    min_latency_ms = min(timings)
    print(
        f"\n[BENCHMARK] 10,000-agent binary pack latency: avg {avg_latency_ms:.3f} ms, "
        f"min {min_latency_ms:.3f} ms (Target: < 2.0 ms)"
    )

    assert avg_latency_ms < 2.0, f"Serialization took {avg_latency_ms:.3f} ms, exceeding 2.0 ms"
    assert len(binary_payload) == 240000, f"Expected 240,000 bytes, got {len(binary_payload)}"

    try:
        # Connect real client and verify binary transfer & round-trip decoding
        async with websockets.connect(f"ws://127.0.0.1:{port}", max_size=1024 * 1024) as ws:
            await bridge.broadcast_binary_async(binary_payload)
            received_bytes = await ws.recv()

            assert isinstance(received_bytes, bytes)
            assert len(received_bytes) == 240000

            # Exact round-trip coordinate and attribute verification
            unpacked = GodotWebSocketBridge.unpack_binary_frame(received_bytes)
            assert unpacked.shape == (10000, 6)
            assert np.allclose(unpacked, expected_data, atol=1e-5)

    finally:
        await bridge.stop_server_async()


@pytest.mark.asyncio
async def test_zero_direct_sqlite_and_live_two_book_edits(tmp_path: Path) -> None:
    """
    Verifies that GOD_LIBRARY_EDIT and GOD_CODEX_APPROVE sent over WebSocket:
    1. Update Python RAM immediately (bypass_god_check=True).
    2. Apply live engine parameter overrides.
    3. Leave data/civilization.db untouched until end-of-day atomic commit.
    4. Malformed frames fail closed and log to ErrorHealer.
    """
    db_path = tmp_path / "civilization.db"
    engine = SimulationEngine(
        db_path=db_path,
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        headless=True,
    )

    port = get_ephemeral_port()
    bridge = GodotWebSocketBridge(host="127.0.0.1", port=port, engine=engine)
    engine.adapter = bridge
    await bridge.start_server_async()

    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            # Step A: GOD_LIBRARY_EDIT
            lib_msg = {
                "type": "GOD_LIBRARY_EDIT",
                "topic": "DIVINE_PHYSICS",
                "volume_title": "Celestial Mechanics Vol I",
                "author_id": "GOD",
                "text_content": "Gravitational curvature is sustained by divine harmonics.",
            }
            await ws.send(json.dumps(lib_msg))
            resp1 = json.loads(await ws.recv())
            assert resp1["type"] == "GOD_LIBRARY_EDIT_RESPONSE"
            assert resp1["status"] == "SUCCESS"

            # Check Python RAM updated immediately
            entries = engine.governance_engine.library_entries
            assert "lib_DIVINE_PHYSICS" in entries
            assert entries["lib_DIVINE_PHYSICS"].title == "Celestial Mechanics Vol I"

            # Verify SQLite DB has ZERO rows for world_library mid-day
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='world_library'"
            )
            table_exists = cur.fetchone() is not None
            if table_exists:
                cur.execute("SELECT COUNT(*) FROM world_library")
                assert cur.fetchone()[0] == 0, "SQLite world_library must NOT be written mid-day!"
            conn.close()

            # Step B: Submit Divine Codex proposal from World Goddess in RAM
            ok, pmsg, prop = engine.governance_engine.submit_parameter_override_proposal(
                title="Divine Truce Pacing",
                text="Extend truce periods during mortal holy seasons.",
                parameter_key="DIVINE_TRUCE_DURATION",
                parameter_value=120.0,
                proposer_slot="world_goddess",
                co_sponsors=[],
                current_tick=engine.current_tick,
            )
            assert ok
            assert prop is not None

            # Approve via WebSocket
            approve_msg = {
                "type": "GOD_CODEX_APPROVE",
                "proposal_id": prop.proposal_id,
            }
            await ws.send(json.dumps(approve_msg))
            resp2 = json.loads(await ws.recv())
            assert resp2["type"] == "GOD_CODEX_APPROVE_RESPONSE"
            assert resp2["status"] == "SUCCESS"

            # Check live engine parameter override applied in RAM
            assert (
                engine.governance_engine.live_engine_overrides["DIVINE_TRUCE_DURATION"]
                == 120.0
            )

            # Step C: Malformed JSON frame handling
            initial_healer_drops = engine.healer.get_fault_count(
                engine.current_day, "WS_BRIDGE_DROP"
            )
            await ws.send("INVALID_JSON_GARBAGE {{{")
            resp_err = json.loads(await ws.recv())
            assert resp_err["type"] == "ERROR"
            assert "Malformed JSON" in resp_err["error"]
            assert (
                engine.healer.get_fault_count(engine.current_day, "WS_BRIDGE_DROP")
                > initial_healer_drops
            )

    finally:
        await bridge.stop_server_async()


def test_speed_control(tmp_path: Path) -> None:
    """
    Verifies that simulation speed accelerates cleanly (1x -> 20x -> 1x)
    without desyncing calendar day or season counters.
    """
    engine = SimulationEngine(
        db_path=tmp_path / "civilization.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        headless=True,
    )

    assert engine.speed == 1.0
    initial_season = engine.current_season

    # Accelerate to 20x
    engine.set_speed(20.0)
    assert engine.speed == 20.0

    # Advance 120 ticks
    for _ in range(120):
        engine.step_tick()

    assert engine.current_tick == 120
    assert engine.current_season == initial_season

    # Slow down back to 1x
    engine.set_speed(1.0)
    assert engine.speed == 1.0


def test_rich_cli_and_duckdb_read_only_analytics(tmp_path: Path) -> None:
    """
    Verifies core Rich God Console inspect/intervene commands and
    DuckDB read-only analytics execution without locking SQLite writer.
    """
    db_path = tmp_path / "civilization.db"
    engine = SimulationEngine(
        db_path=db_path,
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        headless=True,
    )

    # Spawn founders across all 4 races
    founders = []
    for race in ("HUMAN", "ELF", "DRAGON", "BEASTHUMAN"):
        f = engine.spawn_agent(race=race, gender="GIRL", stage="ADULT", initial_credits=50.0)  # type: ignore
        founders.append(f)

    console = RichGodConsole(engine=engine)

    # 1. Inspect status
    status_out = console.execute_command("status")
    assert "Living Agents" in status_out
    assert "Day 1" in status_out

    # 2. Inspect pop
    pop_out = console.execute_command("pop")
    assert "HUMAN" in pop_out
    assert "ELF" in pop_out
    assert "DRAGON" in pop_out
    assert "BEASTHUMAN" in pop_out

    # 3. Intervene: name_deity
    name_out = console.execute_command('name_deity gm_human "Aurelia"')
    assert "Aurelia" in name_out
    assert engine.divine_hierarchy.entities["gm_human"].bestowed_name == "Aurelia"

    # 4. Intervene: speed
    speed_out = console.execute_command("speed 20x")
    assert "20.0x" in speed_out
    assert engine.speed == 20.0

    # 5. Intervene: codex write
    decree_out = console.execute_command('codex write decree_01 "Mortals harvest in peace."')
    assert "decree_01" in decree_out

    # 6. Intervene: codex approve
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

    # 7. Intervene: save
    save_out = console.execute_command("save")
    assert "Atomic save committed successfully" in save_out
    assert engine.current_day == 2

    # 8. DuckDB Analytics (read-only query on civilization.db)
    analytics_out = console.execute_command("analytics demographics")
    assert "DuckDB Analytics: DEMOGRAPHICS" in analytics_out
    assert "HUMAN" in analytics_out

    # Verify DuckDB did not leave any locks preventing live SQLite operations
    # Engine should be able to step and commit again cleanly
    engine.step_tick()
    save_out2 = console.execute_command("save")
    assert "Atomic save committed successfully" in save_out2
    assert engine.current_day == 3
