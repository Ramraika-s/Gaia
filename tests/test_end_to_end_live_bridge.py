"""
tests/test_end_to_end_live_bridge.py
Phase 5 Vertical Slice C End-to-End Live Bridge Integration Test.
Validates:
1. Live real-time WebSocket connection between simulated Godot client and Python core.
2. Binary PackedFloat32Array 5-race frame broadcasting & round-trip unpacking.
3. Live Two-Book synchronization:
   - Initial CLIENT_HANDSHAKE -> HANDSHAKE_ACK + BOOK_STATE_SYNC.
   - Live GOD_LIBRARY_EDIT applied strictly in RAM with zero mid-day SQLite writes.
   - Live GOD_CODEX_APPROVE applying live engine parameter overrides.
   - Live GOD_CODEX_REJECT rejecting codex proposals cleanly.
4. Live In-Game God Console execution via GOD_COMMAND (status, pop).
5. Clean end-of-day World Goddess atomic Two-Phase Commit with SHA-256 verification.
"""

from __future__ import annotations

import json
import socket
import sqlite3
from pathlib import Path

import pytest
import websockets

from sim_core.bridge.godot_ws_bridge import GodotWebSocketBridge
from sim_core.engine import SimulationEngine
from sim_core.god_console.cli import RichGodConsole
from sim_core.schemas import Gender, RaceId, Vec3


def get_ephemeral_port() -> int:
    """Finds an available local port for isolated WebSocket test servers."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.asyncio
async def test_end_to_end_live_bridge_and_ui_sync(tmp_path: Path) -> None:
    db_path = tmp_path / "civilization.db"
    checkpoints_dir = tmp_path / "checkpoints"
    god_ledger_dir = tmp_path / "god_ledger"
    port = get_ephemeral_port()

    # 1. Boot 5-Race SimulationEngine + GodotWebSocketBridge
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

    # Spawn 50 agents across 5 races & 2 genders
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
            # 2. Handshake & Book State Sync
            await ws.send(json.dumps({"type": "CLIENT_HANDSHAKE", "client_version": "4.7.2"}))

            # Expect HANDSHAKE_ACK and BOOK_STATE_SYNC
            resp1 = json.loads(await ws.recv())
            assert resp1["type"] == "HANDSHAKE_ACK"
            assert resp1["status"] == "CONNECTED"

            resp2 = json.loads(await ws.recv())
            assert resp2["type"] == "BOOK_STATE_SYNC"
            assert "library_entries" in resp2
            assert "codex_entries" in resp2
            assert "live_overrides" in resp2

            # 3. Binary 5-Race Frame Broadcast & Unpacking
            payload = bridge.pack_binary_frame()
            assert len(payload) == 50 * 24
            await bridge.broadcast_binary_async(payload)

            bin_data = await ws.recv()
            assert isinstance(bin_data, bytes)
            assert len(bin_data) == 50 * 24

            unpacked = GodotWebSocketBridge.unpack_binary_frame(bin_data)
            assert len(unpacked) == 50
            race_ids = set(unpacked[:, 3].astype(int))
            assert race_ids == {0, 1, 2, 3, 4}  # All 5 races present

            # 4. Live GOD_LIBRARY_EDIT (Strictly in RAM, zero mid-day SQLite writes)
            edit_msg = {
                "type": "GOD_LIBRARY_EDIT",
                "topic": "COSMOLOGY",
                "volume_title": "The Celestial Spheres",
                "author_id": "GOD",
                "text_content": "The universe expands through divine harmonic resonance.",
            }
            await ws.send(json.dumps(edit_msg))

            edit_resp = json.loads(await ws.recv())
            assert edit_resp["type"] == "GOD_LIBRARY_EDIT_RESPONSE"
            assert edit_resp["status"] == "SUCCESS"

            # Check that entry is immediately in RAM
            entries = engine.governance_engine.library_entries
            assert any(e.topic == "COSMOLOGY" for e in entries.values())

            # Verify zero mid-day disk writes to SQLite
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT count(*) FROM world_library WHERE topic = 'COSMOLOGY'")
                row = cursor.fetchone()
                assert row is not None and row[0] == 0, (
                    "Violated Pure End-of-Day rule: SQLite mutated mid-day!"
                )

            # 5. Live GOD_CODEX_APPROVE (Applies Live Engine Parameter Override)
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
            assert prop.status == "PENDING_GOD"

            await ws.send(
                json.dumps({
                    "type": "GOD_CODEX_APPROVE",
                    "proposal_id": prop.proposal_id,
                })
            )

            approve_resp = json.loads(await ws.recv())
            assert approve_resp["type"] == "GOD_CODEX_APPROVE_RESPONSE"
            assert approve_resp["status"] == "SUCCESS"
            assert engine.governance_engine.live_engine_overrides["divine_truce_ticks"] == 6000.0

            # 6. Live GOD_CODEX_REJECT
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
                json.dumps({
                    "type": "GOD_CODEX_REJECT",
                    "proposal_id": prop2.proposal_id,
                })
            )

            reject_resp = json.loads(await ws.recv())
            assert reject_resp["type"] == "GOD_CODEX_REJECT_RESPONSE"
            assert reject_resp["status"] == "SUCCESS"
            assert engine.governance_engine.codex_proposals[prop2.proposal_id].status == "REJECTED"

            # 7. In-Game God Console Raw Commands (GOD_COMMAND)
            await ws.send(json.dumps({"type": "GOD_COMMAND", "raw_command": "status"}))
            cmd_resp1 = json.loads(await ws.recv())
            assert cmd_resp1["type"] == "GOD_COMMAND_RESULT"
            assert cmd_resp1["status"] == "SUCCESS"
            assert "Civilization Status" in cmd_resp1["output"]

            await ws.send(json.dumps({"type": "GOD_COMMAND", "raw_command": "pop"}))
            cmd_resp2 = json.loads(await ws.recv())
            assert cmd_resp2["type"] == "GOD_COMMAND_RESULT"
            assert cmd_resp2["status"] == "SUCCESS"
            for race_name in ["HUMAN", "ELF", "DRAGON", "BEASTHUMAN", "DEMON"]:
                assert race_name in cmd_resp2["output"]

            # 8. Clean End-of-Day World Goddess Atomic Checkpoint
            manifest = engine.commit_end_of_day()
            assert manifest.status == "VERIFIED"
            assert (checkpoints_dir / f"day_{manifest.day:05d}.pt").exists()
            assert (checkpoints_dir / f"day_{manifest.day:05d}.db").exists()
            assert (checkpoints_dir / "manifest.json").exists()

            # Now SQLite has the committed library entry
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT count(*) FROM world_library WHERE topic = 'COSMOLOGY'")
                row = cursor.fetchone()
                assert row is not None and row[0] == 1, (
                    "Committed library entry missing from SQLite after day end!"
                )

    finally:
        await bridge.stop_server_async()
