"""
tests/test_spatial_awareness_speech_and_deity_ai.py
Unit and integration tests for Sprint 5:
1. Spatial awareness & road/doorway navigation, obstacle avoidance, crowd separation.
2. 24-hour utility scheduler & weather interrupt.
3. Semantic speech acts & mechanical consequences (book lore, crimes, price spikes).
4. Autonomous World Goddess & 5 God-Mothers daily agendas and CONVENE_COUNCIL movement.
5. DivineLLMBrain grounded RAG replies in offline fallback and critic action validation.
6. WebSocket bridge DEITY_SYNC and DIALOGUE_REQUEST -> DIALOGUE_RESPONSE round-trip.
"""

from __future__ import annotations

import asyncio
import json
import math
from pathlib import Path

import pytest
import websockets

from sim_core.brains.personality import PersonalityVector
from sim_core.bridge.godot_ws_bridge import GodotWebSocketBridge
from sim_core.bridge.mock_adapter import MockWorldAdapter
from sim_core.engine import SimulationEngine
from sim_core.schemas import (
    AgentRecord,
    DialogueRequest,
    DialogueResponse,
    Vec3,
    WorldLibraryEntry,
)
from sim_core.spatial.hash_grid import SpatialHashGrid
from sim_core.spatial.navigation import BuildingFootprint, NavigationEngine


@pytest.fixture
def test_engine(tmp_path: Path) -> SimulationEngine:
    db = tmp_path / "test_sprint5.db"
    ckpt = tmp_path / "checkpoints"
    ledger = tmp_path / "ledger"
    engine = SimulationEngine(
        db_path=db,
        checkpoints_dir=ckpt,
        god_ledger_dir=ledger,
        adapter=MockWorldAdapter(),
        headless=True,
    )
    return engine


def test_building_obstacle_and_water_avoidance() -> None:
    nav = NavigationEngine(heightmap=None)
    # Register test palace footprint at (0, 0) radius 50m, doorway at (0, 30)
    fp = BuildingFootprint(
        name="Test Palace",
        cx=0.0,
        cz=0.0,
        radius=50.0,
        door_x=0.0,
        door_z=30.0,
        building_type="PALACE",
    )
    nav.footprints = [fp]

    # Try walking directly into the center of the building (from 0, 60 towards 0, 0)
    nx, nz, yaw = nav.resolve_world_movement(
        current_x=0.0,
        current_z=60.0,
        target_x=0.0,
        target_z=0.0,
        speed=20.0,
        dt=1.0,
    )
    # The step would land at (0, 40) which is inside radius 50m. It must be pushed out to >= 51m
    dist_from_center = math.hypot(nx, nz)
    assert dist_from_center >= 50.0, f"Mortal penetrated building! Dist={dist_from_center}"


def test_vectorized_crowd_separation() -> None:
    nav = NavigationEngine(heightmap=None)
    grid = SpatialHashGrid(cell_size=16.0)

    # Place two agents directly on top of each other at (100.0, 100.0)
    a1 = AgentRecord(
        agent_id="agent_1",
        slot_idx=0,
        display_name="Citizen 1",
        dynasty_surname="Alpha",
        gender="BOY",
        race="HUMAN",
        pos=Vec3(x=100.0, y=20.0, z=100.0),
    )
    a2 = AgentRecord(
        agent_id="agent_2",
        slot_idx=1,
        display_name="Citizen 2",
        dynasty_surname="Beta",
        gender="GIRL",
        race="ELF",
        pos=Vec3(x=100.05, y=20.0, z=100.05),
    )
    agents = [a1, a2]
    grid.update_agent(a1.agent_id, a1.pos.x, a1.pos.z)
    grid.update_agent(a2.agent_id, a2.pos.x, a2.pos.z)

    # Initial distance is ~0.07m (< 0.85m)
    init_dist = math.hypot(a1.pos.x - a2.pos.x, a1.pos.z - a2.pos.z)
    assert init_dist < 0.15

    # Run crowd separation passes
    for _ in range(5):
        nav.apply_crowd_separation(agents, grid, personal_space=0.85, repulsion_factor=0.5)
        grid.update_agent(a1.agent_id, a1.pos.x, a1.pos.z)
        grid.update_agent(a2.agent_id, a2.pos.x, a2.pos.z)

    sep_dist = math.hypot(a1.pos.x - a2.pos.x, a1.pos.z - a2.pos.z)
    assert sep_dist >= 0.80, f"Crowd separation failed! Final dist={sep_dist:.3f}m"


def test_god_presence_reaction() -> None:
    nav = NavigationEngine(heightmap=None)
    # Agent near God Avatar (< 6.0m)
    agent = AgentRecord(
        agent_id="mortal_devout",
        slot_idx=0,
        display_name="Brother Vael",
        dynasty_surname="Solaris",
        gender="BOY",
        race="HUMAN",
        pos=Vec3(x=1.0, y=24.0, z=0.0),
    )
    from sim_core.brains.personality import PersonalityVector

    agent.personality = PersonalityVector(devotion=0.85)

    god_pos = Vec3(x=0.0, y=24.0, z=0.0)
    reacted = nav.apply_god_presence_reaction([agent], god_pos, presence_radius=6.0)
    assert reacted == 1
    # Check that agent was pushed back to clear path and faced God
    assert agent.pos.x >= 1.15
    assert agent.activity_state == "BOWING"


def test_24_hour_utility_scheduler_and_weather_interrupt() -> None:
    nav = NavigationEngine(heightmap=None)
    agent = AgentRecord(
        agent_id="test_worker",
        slot_idx=0,
        display_name="Master Karl",
        dynasty_surname="Forge",
        gender="BOY",
        race="HUMAN",
        profession="SCHOLAR",
        pos=Vec3(x=10.0, y=24.0, z=10.0),
    )

    # Morning (07:00 AM -> 7 * 450 = 3150 ticks)
    activity_m, _ = nav.evaluate_utility_schedule(agent, tick=3150, weather="CLEAR")
    assert activity_m == "MORNING_PREP"

    # Day (12:00 PM -> 12 * 450 = 5400 ticks)
    activity_d, target_d = nav.evaluate_utility_schedule(agent, tick=5400, weather="CLEAR")
    assert activity_d == "STUDYING"  # Scholar goes to Library
    assert target_d is not None and target_d.x == 180.0 and target_d.z == 180.0

    # Evening (19:00 -> 19 * 450 = 8550 ticks)
    agent.personality = PersonalityVector(devotion=0.8)
    activity_e, _ = nav.evaluate_utility_schedule(agent, tick=8550, weather="CLEAR")
    assert activity_e == "EVENING_PRAYER"

    # Night (23:00 -> 23 * 450 = 10350 ticks)
    activity_n, _ = nav.evaluate_utility_schedule(agent, tick=10350, weather="CLEAR")
    assert activity_n == "SLEEPING"

    # Weather Interrupt (STORM -> seeks shelter immediately regardless of hour)
    activity_storm, _ = nav.evaluate_utility_schedule(agent, tick=5400, weather="STORM")
    assert activity_storm == "SHELTERING"


def test_semantic_speech_acts_and_mechanical_consequences(test_engine: SimulationEngine) -> None:
    engine = test_engine
    speech = engine.speech_acts

    # Create Scholar mentor and apprentice
    mentor = engine.spawn_agent(
        race="HUMAN", gender="BOY", stage="ADULT", pos=Vec3(x=50.0, y=24.0, z=50.0)
    )
    apprentice = engine.spawn_agent(
        race="HUMAN", gender="GIRL", stage="ADULT", pos=Vec3(x=52.0, y=24.0, z=50.0)
    )

    # Add a book to the World Library
    book = WorldLibraryEntry(
        entry_id="lib_agr_crop_rotation",
        topic="AGRICULTURE",
        title="Principles of Crop Rotation",
        summary="Triennial rotation increases barley yield.",
        author_id="Founder",
        author_proficiency=1.0,
        skill_bonus=0.15,
        mechanical_effects={"farming": 0.15},
        created_tick=1,
    )
    engine.governance_engine.library_entries[book.entry_id] = book
    mentor.known_books.append(book.entry_id)

    # Execute SHARE_BOOK_LORE speech act
    speech.emit_speech_act(
        speaker=mentor,
        act_type="SHARE_BOOK_LORE",
        topic=book.entry_id,
        listener=apprentice,
    )
    assert book.entry_id in apprentice.known_books
    assert apprentice.active_mechanical_effects.get("farming", 0.0) >= 0.15

    # Execute REPORT_CRIME speech act
    guard = engine.spawn_agent(
        race="HUMAN", gender="BOY", stage="ADULT", pos=Vec3(x=53.0, y=24.0, z=50.0)
    )
    guard.profession = "CITY_GUARD"

    speech.emit_speech_act(
        speaker=mentor,
        act_type="REPORT_CRIME",
        topic="THEFT",
        listener=guard,
    )
    assert guard.activity_state == "INTERCEPT_CRIME"

    # Execute WARN_PRICE_SPIKE speech act
    speech.emit_speech_act(
        speaker=mentor,
        act_type="WARN_PRICE_SPIKE",
        topic="GRAIN",
        listener=apprentice,
    )
    # Verify memory was logged
    mems = engine.memory_rag.get_recent_memories(apprentice.agent_id)
    assert any("Heard from" in m.summary for m in mems)


def test_autonomous_deities_and_convene_council(test_engine: SimulationEngine) -> None:
    engine = test_engine
    autonomy = engine.divine_autonomy

    # Check all 6 deities exist
    assert len(autonomy.deities) == 6
    goddess = autonomy.deities["world_goddess"]
    gm_human = autonomy.deities["gm_human"]
    gm_dragon = autonomy.deities["gm_dragon"]

    assert goddess.name == "World Goddess"
    assert gm_human.race == "HUMAN"
    assert gm_dragon.race == "DRAGON"

    # Step simulation
    autonomy.step(current_tick=10)
    records = autonomy.get_sync_records()
    assert len(records) == 6

    # Issue God order CONVENE_COUNCIL
    result = autonomy.issue_god_order("CONVENE_COUNCIL")
    assert "council" in result.lower()

    # Verify all 5 God-Mothers switched target to Palace Courtyard (0, 15)
    for slot, deity in autonomy.deities.items():
        if slot != "world_goddess":
            assert deity.current_agenda == "CONVENE_COUNCIL"
            assert deity.target_pos is not None
            dist_to_courtyard = math.hypot(deity.target_pos.x - 0.0, deity.target_pos.z - 15.0)
            assert dist_to_courtyard <= 10.0, (
                f"Deity {slot} not at Courtyard: dist={dist_to_courtyard}"
            )


def test_divine_llm_brain_offline_fallback_and_critic(test_engine: SimulationEngine) -> None:
    engine = test_engine
    brain = engine.divine_llm_brain

    # 1. Dialogue with World Goddess
    req = DialogueRequest(
        target_type="DEITY",
        target_id="world_goddess",
        message="Tell me the state of the world.",
        order="NONE",
    )
    resp: DialogueResponse = brain.generate_dialogue(req)
    assert resp.target_id == "world_goddess"
    assert (
        "realm numbers" in resp.spoken_reply.lower()
        or "peace be with you" in resp.spoken_reply.lower()
    )

    # 2. Dialogue with God-Mother
    req_gm = DialogueRequest(
        target_type="DEITY",
        target_id="gm_elf",
        message="How is Sylvanor?",
        order="NONE",
    )
    resp_gm = brain.generate_dialogue(req_gm)
    assert "sylvanor" in resp_gm.spoken_reply.lower()

    # 3. Action validation fail-closed
    assert (
        brain._validate_proposed_action("world_goddess", {"action_type": "MINT_CREDITS"}) is False
    )
    assert (
        brain._validate_proposed_action("world_goddess", {"action_type": "DESTROY_CITY"}) is False
    )
    assert (
        brain._validate_proposed_action("world_goddess", {"action_type": "BLESS_HARVEST"}) is True
    )


@pytest.mark.asyncio
async def test_websocket_deity_sync_and_dialogue_roundtrip(test_engine: SimulationEngine) -> None:
    engine = test_engine
    bridge = GodotWebSocketBridge(host="127.0.0.1", port=18765, engine=engine)
    await bridge.start_server_async()
    await asyncio.sleep(0.1)

    uri = "ws://127.0.0.1:18765"
    async with websockets.connect(uri) as ws:
        # Handshake
        await ws.send(json.dumps({"type": "CLIENT_HANDSHAKE", "include_deities": True}))

        # Expect HANDSHAKE_ACK, BOOK_STATE_SYNC, BUILDING_SYNC, and DEITY_SYNC
        msgs = []
        for _ in range(4):
            raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
            data = json.loads(raw)
            msgs.append(data.get("type"))

        assert "HANDSHAKE_ACK" in msgs
        assert "DEITY_SYNC" in msgs

        # Send DIALOGUE_REQUEST
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
