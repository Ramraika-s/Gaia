"""
tests/bridge/test_ws_protocol_and_dialogue.py
Tests WebSocket bridge protocol, framing, non-blocking dialogue dispatch, and live sync.
"""

from __future__ import annotations

import asyncio
import json
import socket
import sqlite3
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
import websockets

from sim_core.bridge.godot_ws_bridge import (
    FLAG_CRYING,
    FLAG_IS_ORACLE,
    GodotWebSocketBridge,
)
from sim_core.bridge.protocol import (
    PROTOCOL_VERSION,
    SEASON_PROGRESS_RANGE,
    TIME_OF_DAY_RANGE,
    build_world_time_weather_payload,
    extract_god_command_params,
    normalize_codex_edit_payload,
    normalize_library_edit_payload,
)
from sim_core.engine import SimulationEngine
from sim_core.god_console.cli import RichGodConsole
from sim_core.schemas import (
    DialogueRequest,
    DialogueResponse,
    Gender,
    RaceId,
    Vec3,
    WorldLibraryEntry,
)

STRING_FIELDS = ("dynasty", "dragon_form", "speech_text", "role", "profession", "name")


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


@pytest.mark.benchmark
@pytest.mark.slow
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
    expected_data[:, 0] = np.linspace(-4000.0, 4000.0, n_agents, dtype="<f4")
    expected_data[:, 1] = np.linspace(10.0, 500.0, n_agents, dtype="<f4")
    expected_data[:, 2] = np.linspace(-4000.0, 4000.0, n_agents, dtype="<f4")
    expected_data[:, 3] = (np.arange(n_agents) % 4).astype("<f4")
    expected_data[:, 4] = (np.arange(n_agents) % 4).astype("<f4")
    expected_data[:, 5] = ((np.arange(n_agents) % 2) * (FLAG_CRYING | FLAG_IS_ORACLE)).astype("<f4")

    bridge._ensure_capacity(n_agents)
    bridge.positions[:n_agents] = expected_data
    bridge.active_mask[:n_agents] = True

    # Benchmark serialization latency
    timings: list[float] = []
    binary_payload = b""
    for _ in range(10):
        t0 = time.perf_counter()
        binary_payload = bridge.pack_binary_frame()
        t1 = time.perf_counter()
        timings.append((t1 - t0) * 1000.0)

    avg_latency_ms = sum(timings) / len(timings)
    assert avg_latency_ms < 2.5, f"Serialization took {avg_latency_ms:.3f} ms, exceeding 2.5 ms"
    assert len(binary_payload) == 240000, f"Expected 240,000 bytes, got {len(binary_payload)}"

    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}", max_size=1024 * 1024) as ws:
            await bridge.broadcast_binary_async(binary_payload)
            received_bytes = await ws.recv()

            assert isinstance(received_bytes, bytes)
            assert len(received_bytes) == 240000

            unpacked = GodotWebSocketBridge.unpack_binary_frame(received_bytes)
            assert unpacked.shape == (10000, 6)
            assert np.allclose(unpacked, expected_data, atol=1e-5)
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


def test_bubble_sync_never_contains_none_strings(engine: SimulationEngine) -> None:
    adult = engine.spawn_agent("HUMAN", "BOY", stage="ADULT", pos=Vec3(x=1.0, y=0.0, z=1.0))
    dragon = engine.spawn_agent("DRAGON", "GIRL", stage="ADULT", pos=Vec3(x=2.0, y=0.0, z=2.0))
    for agent in (adult, dragon):
        object.__setattr__(agent, "dynasty_surname", None)
        object.__setattr__(agent, "role", None)
        object.__setattr__(agent, "speech_text", None)
    object.__setattr__(adult, "profession", "")
    object.__setattr__(dragon, "profession", "")
    object.__setattr__(adult, "dragon_form", None)
    object.__setattr__(dragon, "dragon_form", None)

    engine.step_tick()
    rigs: list[dict[str, Any]] = engine.adapter.bubble_agents  # type: ignore[attr-defined]
    assert len(rigs) >= 2
    for rig in rigs:
        for key in STRING_FIELDS:
            assert rig[key] is not None, f"{key} is None in BUBBLE_SYNC"
            assert isinstance(rig[key], str)
        assert rig["role"] != "" and rig["profession"] != "" and rig["dragon_form"] != ""
        json.dumps(rig)
    assert rigs[0]["dynasty"] == ""
    assert rigs[0]["speech_text"] == ""
    assert rigs[0]["dragon_form"] == "HUMANOID_DRAGON"


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
async def test_dialogue_request_does_not_block_god_commands(engine: SimulationEngine) -> None:
    def slow_generate(req: DialogueRequest) -> DialogueResponse:
        time.sleep(0.3)
        return DialogueResponse(
            target_id=req.target_id,
            target_name="Gaia",
            title="World Goddess",
            race="DIVINE",
            mood="calm",
            spoken_reply="Peace, My Lord.",
            action_taken="",
            llm_backend="OFFLINE_FALLBACK",
        )

    engine.divine_llm_brain = SimpleNamespace(generate_dialogue=slow_generate)  # type: ignore[assignment]
    port = get_ephemeral_port()
    bridge = GodotWebSocketBridge(host="127.0.0.1", port=port, engine=engine)
    await bridge.start_server_async()
    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            t0 = time.monotonic()
            await ws.send(
                json.dumps(
                    {
                        "type": "DIALOGUE_REQUEST",
                        "dialogue_id": "slow_1",
                        "target_type": "DEITY",
                        "target_id": "world_goddess",
                        "message": "Greetings",
                        "order": "",
                    }
                )
            )
            await ws.send(json.dumps({"type": "GOD_STATE", "x": 3.0, "y": 1.0, "z": 4.0}))
            await ws.send(json.dumps({"type": "GOD_COMMAND", "command": "pause", "args": {}}))

            arrivals: list[tuple[str, float]] = []
            while len(arrivals) < 3:
                raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
                msg = json.loads(raw)
                arrivals.append((msg["type"], time.monotonic() - t0))

            by_type = dict(arrivals)
            assert "DIALOGUE_RESPONSE" in by_type
            assert "GOD_STATE_ACK" in by_type
            assert "GOD_COMMAND_RESPONSE" in by_type
            assert by_type["GOD_STATE_ACK"] < 0.25
            assert by_type["GOD_COMMAND_RESPONSE"] < 0.25
            assert by_type["DIALOGUE_RESPONSE"] >= 0.28
            assert arrivals[-1][0] == "DIALOGUE_RESPONSE"
        assert engine.god_avatar_pos.x == 3.0
    finally:
        await bridge.stop_server_async()
    assert not bridge._background_tasks


@pytest.mark.asyncio
async def test_handle_inbound_dialogue_is_awaitable_with_flush(engine: SimulationEngine) -> None:
    port = get_ephemeral_port()
    bridge = GodotWebSocketBridge(host="127.0.0.1", port=port, engine=engine)
    sent: list[dict[str, Any]] = []

    class FakeClient:
        async def send(self, payload: str) -> None:
            sent.append(json.loads(payload))

    msg = json.dumps(
        {
            "type": "DIALOGUE_REQUEST",
            "target_type": "DEITY",
            "target_id": "world_goddess",
            "message": "Give me a report on the world.",
        }
    )
    await bridge.handle_inbound_message(FakeClient(), msg)  # type: ignore[arg-type]
    await bridge.flush_background_tasks()
    assert [m["type"] for m in sent] == ["DIALOGUE_RESPONSE"]
    assert sent[0]["spoken_reply"].strip() != ""
    assert not bridge._background_tasks


@pytest.mark.asyncio
async def test_disconnect_cancels_inflight_dialogue(engine: SimulationEngine) -> None:
    def very_slow(req: DialogueRequest) -> DialogueResponse:
        time.sleep(0.04)
        return DialogueResponse(
            target_id=req.target_id,
            target_name="X",
            title="T",
            race="DIVINE",
            mood="calm",
            spoken_reply="late",
            action_taken="",
        )

    engine.divine_llm_brain = SimpleNamespace(generate_dialogue=very_slow)  # type: ignore[assignment]
    port = get_ephemeral_port()
    bridge = GodotWebSocketBridge(host="127.0.0.1", port=port, engine=engine)
    await bridge.start_server_async()
    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send(
                json.dumps(
                    {"type": "DIALOGUE_REQUEST", "target_type": "DEITY", "target_id": "gm_elf"}
                )
            )
            await asyncio.sleep(0.02)
            assert bridge._background_tasks
        await asyncio.sleep(0.1)
        assert not bridge._background_tasks
    finally:
        await bridge.stop_server_async()


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
    bridge.clients.add(broken)  # type: ignore[arg-type]
    engine.god_presence.set_active(True)
    assert len(bridge.clients) == 1
    assert engine.god_presence.is_active

    await bridge.broadcast_binary_async(b"test_payload")
    assert len(bridge.clients) == 0
    assert not engine.god_presence.is_active

    broken2 = BrokenClient()
    bridge.clients.add(broken2)  # type: ignore[arg-type]
    engine.god_presence.set_active(True)

    await bridge.broadcast_json_async({"type": "TEST"})
    assert len(bridge.clients) == 0
    assert not engine.god_presence.is_active


@pytest.mark.asyncio
async def test_websocket_deity_sync_and_dialogue_roundtrip(engine: SimulationEngine) -> None:
    port = get_ephemeral_port()
    bridge = GodotWebSocketBridge(host="127.0.0.1", port=port, engine=engine)
    await bridge.start_server_async()
    await asyncio.sleep(0.05)

    uri = f"ws://127.0.0.1:{port}"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"type": "CLIENT_HANDSHAKE", "include_deities": True}))

        msgs: list[str] = []
        for _ in range(4):
            raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
            data = json.loads(raw)
            msgs.append(data.get("type", ""))

        assert "HANDSHAKE_ACK" in msgs
        assert "DEITY_SYNC" in msgs

        dlg_req = {
            "type": "DIALOGUE_REQUEST",
            "dialogue_id": "test_dlg_123",
            "target_type": "DEITY",
            "target_id": "world_goddess",
            "message": "Report on the world's mortal petitions.",
            "order": "",
        }
        await ws.send(json.dumps(dlg_req))

        raw_resp = await asyncio.wait_for(ws.recv(), timeout=3.0)
        resp_data = json.loads(raw_resp)
        assert resp_data.get("type") == "DIALOGUE_RESPONSE"
        assert resp_data.get("target_id") == "world_goddess"
        assert len(resp_data.get("spoken_reply", "")) > 10

    await bridge.stop_server_async()


@pytest.mark.asyncio
async def test_end_to_end_live_bridge_and_ui_sync(tmp_path: Path) -> None:
    """Full live WebSocket roundtrip for multi-race sync, book edits, and god commands."""
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

    races: list[RaceId] = ["HUMAN", "ELF", "DRAGON", "BEASTHUMAN", "DEMON"]
    genders: list[Gender] = ["BOY", "GIRL"]
    for i in range(50):
        race = races[i % 5]
        gender = genders[i % 2]
        engine.spawn_agent(
            race=race,
            gender=gender,
            stage="ADULT",
            pos=Vec3(x=float(i * 10), y=18.0, z=float(i * 10)),
            initial_credits=25.0,
        )

    await bridge.start_server_async()

    try:
        uri = f"ws://127.0.0.1:{port}"
        async with websockets.connect(uri, max_size=1024 * 1024) as ws:
            await ws.send(json.dumps({"type": "CLIENT_HANDSHAKE", "client_version": "4.7.2"}))

            resp1 = json.loads(await ws.recv())
            assert resp1["type"] == "HANDSHAKE_ACK"
            assert resp1["status"] == "CONNECTED"

            resp2 = json.loads(await ws.recv())
            assert resp2["type"] == "BOOK_STATE_SYNC"

            resp3 = json.loads(await ws.recv())
            assert resp3["type"] == "BUILDING_SYNC"

            payload = bridge.pack_binary_frame()
            assert len(payload) == 50 * 24
            await bridge.broadcast_binary_async(payload)

            bin_data = await ws.recv()
            assert isinstance(bin_data, bytes)
            assert len(bin_data) == 50 * 24

            unpacked = GodotWebSocketBridge.unpack_binary_frame(bin_data)
            assert len(unpacked) == 50
            race_ids = set(unpacked[:, 3].astype(int))
            assert race_ids == {0, 1, 2, 3, 4}

            # GOD_LIBRARY_EDIT
            edit_msg = {
                "type": "GOD_LIBRARY_EDIT",
                "topic": "COSMOLOGY",
                "volume_title": "The Celestial Spheres",
                "text_content": "The universe expands through divine harmonic resonance.",
                "author_id": "GOD",
                "bypass_god_check": True,
                "timestamp": 1700000000.0,
            }
            await ws.send(json.dumps(edit_msg))

            edit_resp = json.loads(await ws.recv())
            assert edit_resp["type"] == "GOD_LIBRARY_EDIT_RESPONSE"
            assert edit_resp["status"] == "SUCCESS"

            sync_resp = json.loads(await ws.recv())
            assert sync_resp["type"] == "BOOK_STATE_SYNC"
            titles = [e.get("title") for e in sync_resp["library_entries"]]
            assert "The Celestial Spheres" in titles

            entries = engine.governance_engine.library_entries
            assert any(
                (e.topic if isinstance(e, WorldLibraryEntry) else e.subject) == "COSMOLOGY"
                for e in entries.values()
            )

            # SQLite untouched mid-day
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT count(*) FROM world_library WHERE topic = 'COSMOLOGY'")
                row = cursor.fetchone()
                assert row is not None and row[0] == 0

            # GOD_CODEX_APPROVE
            success, _, prop = engine.governance_engine.submit_parameter_override_proposal(
                title="Divine Truce Duration",
                text="Increase divine truce ticks during planetary alignment",
                parameter_key="divine_truce_ticks",
                parameter_value=6000.0,
                proposer_slot="world_goddess",
                co_sponsors=[],
                current_tick=engine.current_tick,
            )
            assert success and prop is not None

            await ws.send(
                json.dumps(
                    {
                        "type": "GOD_CODEX_APPROVE",
                        "proposal_id": prop.proposal_id,
                        "timestamp": 1700000001.0,
                    }
                )
            )

            approve_resp = json.loads(await ws.recv())
            assert approve_resp["type"] == "GOD_CODEX_APPROVE_RESPONSE"
            assert approve_resp["status"] == "SUCCESS"
            assert engine.governance_engine.live_engine_overrides["divine_truce_ticks"] == 6000.0

            sync_approve = json.loads(await ws.recv())
            assert sync_approve["type"] == "BOOK_STATE_SYNC"

            # GOD_CODEX_REJECT
            success2, _, prop2 = engine.governance_engine.submit_parameter_override_proposal(
                title="Extravagant Energy Budget",
                text="Triple daily divine energy replenishment",
                parameter_key="daily_energy_multiplier",
                parameter_value=3.0,
                proposer_slot="world_goddess",
                co_sponsors=[],
                current_tick=engine.current_tick,
            )
            assert success2 and prop2 is not None

            await ws.send(
                json.dumps(
                    {
                        "type": "GOD_CODEX_REJECT",
                        "proposal_id": prop2.proposal_id,
                        "timestamp": 1700000002.0,
                    }
                )
            )

            reject_resp = json.loads(await ws.recv())
            assert reject_resp["type"] == "GOD_CODEX_REJECT_RESPONSE"
            assert reject_resp["status"] == "SUCCESS"
            assert engine.governance_engine.codex_proposals[prop2.proposal_id].status == "REJECTED"

            await ws.recv()  # sync

            # GOD_COMMAND execution
            await ws.send(json.dumps({"type": "GOD_COMMAND", "raw_command": "status"}))
            cmd_resp1 = json.loads(await ws.recv())
            assert cmd_resp1["type"] == "GOD_COMMAND_RESULT"
            assert cmd_resp1["status"] == "SUCCESS"

            # End of day commit
            manifest = engine.commit_end_of_day()
            assert manifest.status == "VERIFIED"
            assert (checkpoints_dir / f"day_{manifest.day:05d}.pt").exists()
    finally:
        await bridge.stop_server_async()


@pytest.mark.asyncio
async def test_zero_direct_sqlite_and_live_two_book_edits(tmp_path: Path) -> None:
    """Verifies live RAM updates and zero mid-day SQLite writes."""
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
            await ws.recv()  # BOOK_STATE_SYNC

            entries = engine.governance_engine.library_entries
            assert "lib_DIVINE_PHYSICS" in entries

            # Malformed JSON frame handling
            initial_healer_drops = engine.healer.get_fault_count(
                engine.current_day, "WS_BRIDGE_DROP"
            )
            await ws.send("INVALID_JSON_GARBAGE {{{")
            resp_err = json.loads(await ws.recv())
            assert resp_err["type"] == "ERROR"
            assert (
                engine.healer.get_fault_count(engine.current_day, "WS_BRIDGE_DROP")
                > initial_healer_drops
            )
    finally:
        await bridge.stop_server_async()


@pytest.mark.asyncio
async def test_multi_volume_library_edit_preservation(tmp_path: Path) -> None:
    """Verifies writing two differently titled volumes under the same topic preserves both."""
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
            await ws.recv()  # BOOK_STATE_SYNC

            entries = engine.governance_engine.library_entries
            titles = [
                e.title if isinstance(e, WorldLibraryEntry) else getattr(e, "title", "")
                for e in entries.values()
            ]
            assert "First Principles of Being" in titles
            assert "The Void and Potentiality" in titles
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
    finally:
        await bridge.stop_server_async()

