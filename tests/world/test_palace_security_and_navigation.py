# tests/world/test_palace_security_and_navigation.py
from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from sim_core.brains.personality import PersonalityVector
from sim_core.bridge.mock_adapter import MockWorldAdapter
from sim_core.divine.god_ledger import GodLedgerPipeline, GodPresenceTracker
from sim_core.engine import SimulationEngine
from sim_core.persistence.world_goddess import WorldGoddessCritic
from sim_core.schemas import AgentRecord, PalacePass, Vec3
from sim_core.society.judiciary import JudiciaryEngine
from sim_core.spatial.hash_grid import SpatialHashGrid
from sim_core.spatial.navigation import BuildingFootprint, NavigationEngine
from sim_core.world.palace_security import (
    DRAGON_LEFT_X,
    DRAGON_LEFT_Y,
    DRAGON_LEFT_Z,
    MAIN_GATE_X,
    MAIN_GATE_Y,
    MAIN_GATE_Z,
    OUTER_BOUNDARY_RADIUS,
    PALACE_CENTER_Y,
    PalaceSecurityEngine,
)


@pytest.fixture
def mock_security_env(
    tmp_path: Path,
) -> tuple[
    PalaceSecurityEngine,
    GodPresenceTracker,
    GodLedgerPipeline,
    WorldGoddessCritic,
    JudiciaryEngine,
    MockWorldAdapter,
]:
    """Provides an isolated PalaceSecurityEngine fixture with mock adapter and pipeline."""
    presence = GodPresenceTracker()
    ledger = GodLedgerPipeline(ledger_dir=str(tmp_path / "ledger"), tracker=presence)
    goddess = WorldGoddessCritic()
    judiciary = JudiciaryEngine()
    adapter = MockWorldAdapter()

    security = PalaceSecurityEngine(
        engine=None,
        god_presence=presence,
        ledger_pipeline=ledger,
        world_goddess=goddess,
        judiciary=judiciary,
        adapter=adapter,
    )
    return security, presence, ledger, goddess, judiciary, adapter


def test_whitelist_bypass(
    mock_security_env: tuple[PalaceSecurityEngine, Any, Any, Any, Any, Any],
) -> None:
    """God, Goddess, 5 God-Mothers, and Palace Knights must bypass security checks."""
    security, _, _, _, _, _ = mock_security_env

    for deity in [
        "god_avatar",
        "world_goddess",
        "gm_human",
        "gm_elf",
        "gm_dragon",
        "gm_beasthuman",
        "gm_demon",
    ]:
        assert security.is_whitelisted(deity) is True

    knight = AgentRecord(
        agent_id="knight_01",
        slot_idx=0,
        display_name="Sir Lancelot",
        dynasty_surname="Guard",
        gender="BOY",
        race="HUMAN",
        role="PALACE_KNIGHT",
        pos=Vec3(x=MAIN_GATE_X, y=MAIN_GATE_Y, z=MAIN_GATE_Z),
    )
    assert security.is_whitelisted(knight) is True

    mortal = AgentRecord(
        agent_id="mortal_01",
        slot_idx=1,
        display_name="Alice",
        dynasty_surname="Smith",
        gender="GIRL",
        race="HUMAN",
        role="CITIZEN",
        pos=Vec3(x=MAIN_GATE_X, y=MAIN_GATE_Y, z=MAIN_GATE_Z),
    )
    assert security.is_whitelisted(mortal) is False


def test_mortal_petition_halt_when_god_active(
    mock_security_env: tuple[
        PalaceSecurityEngine,
        GodPresenceTracker,
        Any,
        Any,
        Any,
        MockWorldAdapter,
    ],
) -> None:
    """Mortal entering 35m Gate Zone is halted and emits PALACE_ENTRY_REQUEST when God is active."""
    security, presence, _, _, _, adapter = mock_security_env
    presence.set_active(True, tick=10)

    mortal = AgentRecord(
        agent_id="mortal_petitioner_01",
        slot_idx=1,
        display_name="Theron",
        dynasty_surname="The Bold",
        gender="BOY",
        race="ELF",
        role="CITIZEN",
        pos=Vec3(x=MAIN_GATE_X, y=MAIN_GATE_Y, z=MAIN_GATE_Z + 10.0),
        stamina=50.0,
    )
    agents = {mortal.agent_id: mortal}

    security.step(current_tick=10, agents=agents)
    assert mortal.stamina < 50.0

    assert mortal.agent_id in security.agent_to_request
    req_id = security.agent_to_request[mortal.agent_id]
    req = security.pending_requests[req_id]
    assert req.name == "Theron"
    assert req.race == "ELF"
    assert req.status == "PENDING"

    request_events = [e for e in adapter.events if e[0] == "PALACE_ENTRY_REQUEST"]
    assert len(request_events) >= 1
    assert request_events[-1][1]["agent_id"] == "mortal_petitioner_01"


def test_live_god_decision_grant_and_deny(
    mock_security_env: tuple[
        PalaceSecurityEngine,
        GodPresenceTracker,
        GodLedgerPipeline,
        Any,
        Any,
        Any,
    ],
) -> None:
    """When God is active, GOD_PALACE_DECISION grants pass or triggers knight escort."""
    security, presence, ledger, _, _, _ = mock_security_env
    presence.set_active(True, tick=20)

    mortal = AgentRecord(
        agent_id="mortal_grantee",
        slot_idx=2,
        display_name="Lyra",
        dynasty_surname="Starlight",
        gender="GIRL",
        race="ELF",
        role="CITIZEN",
        pos=Vec3(x=MAIN_GATE_X, y=MAIN_GATE_Y, z=MAIN_GATE_Z + 5.0),
    )
    req = security.request_entry(mortal, current_tick=20)

    # 1. God GRANTS entry
    resolved = security.resolve_request(
        request_id=req.request_id,
        decision="GRANT",
        decided_by="GOD",
        current_tick=20,
        duration_ticks=600,
    )
    assert resolved is not None
    assert resolved.status == "GRANTED"
    assert security.has_active_pass(mortal.agent_id, current_tick=20) is True
    assert security.has_active_pass(mortal.agent_id, current_tick=650) is False

    ledger_entries = [e for e in ledger.buffer if e.category == "PALACE_SECURITY"]
    assert len(ledger_entries) >= 1
    assert "granted" in ledger_entries[-1].message.lower()

    # 2. Another mortal DENIED by God
    mortal2 = AgentRecord(
        agent_id="mortal_denied",
        slot_idx=3,
        display_name="Brog",
        dynasty_surname="Ironfist",
        gender="BOY",
        race="BEASTHUMAN",
        role="CITIZEN",
        pos=Vec3(x=MAIN_GATE_X, y=MAIN_GATE_Y, z=MAIN_GATE_Z + 5.0),
    )
    req2 = security.request_entry(mortal2, current_tick=30)
    resolved2 = security.resolve_request(
        request_id=req2.request_id,
        decision="DENY",
        decided_by="GOD",
        current_tick=30,
    )
    assert resolved2 is not None
    assert resolved2.status == "DENIED"
    assert security.has_active_pass(mortal2.agent_id, current_tick=30) is False


def test_goddess_auto_adjudication_when_god_away(
    mock_security_env: tuple[
        PalaceSecurityEngine,
        GodPresenceTracker,
        GodLedgerPipeline,
        Any,
        JudiciaryEngine,
        Any,
    ],
) -> None:
    """When God is AWAY, World Goddess auto-adjudicates: devout clean granted, criminals denied."""
    security, presence, ledger, _, judiciary, _ = mock_security_env
    presence.set_active(False)

    devout = AgentRecord(
        agent_id="devout_citizen",
        slot_idx=4,
        display_name="Brother Paul",
        dynasty_surname="Faithful",
        gender="BOY",
        race="HUMAN",
        role="CLERIC",
        pos=Vec3(x=MAIN_GATE_X, y=MAIN_GATE_Y, z=MAIN_GATE_Z + 15.0),
        godmother_affinities={"gm_human": 0.8},
        patron_godmother_slot="gm_human",
    )

    criminal = AgentRecord(
        agent_id="bandit_joe",
        slot_idx=5,
        display_name="Joe",
        dynasty_surname="The Thief",
        gender="BOY",
        race="HUMAN",
        role="CITIZEN",
        pos=Vec3(x=MAIN_GATE_X, y=MAIN_GATE_Y, z=MAIN_GATE_Z + 20.0),
    )
    judiciary.criminal_records[criminal.agent_id] = ["case_theft_01"]

    agents = {devout.agent_id: devout, criminal.agent_id: criminal}
    security.step(current_tick=50, agents=agents)

    assert security.has_active_pass(devout.agent_id, current_tick=50) is True
    assert security.has_active_pass(criminal.agent_id, current_tick=50) is False

    ledger_entries = [e for e in ledger.buffer if e.category == "PALACE_SECURITY"]
    assert len(ledger_entries) >= 2


def test_trespass_fear_aura_and_judiciary_arrest(
    mock_security_env: tuple[
        PalaceSecurityEngine,
        Any,
        Any,
        Any,
        JudiciaryEngine,
        MockWorldAdapter,
    ],
) -> None:
    """Trespass into 95m Inner Palace Sanctuary triggers fear aura & files Judiciary case."""
    security, _, _, _, judiciary, adapter = mock_security_env

    trespasser = AgentRecord(
        agent_id="intruder_shadow",
        slot_idx=6,
        display_name="Shadow",
        dynasty_surname="Infiltrator",
        gender="BOY",
        race="DEMON",
        role="CITIZEN",
        pos=Vec3(x=DRAGON_LEFT_X + 2.0, y=DRAGON_LEFT_Y, z=DRAGON_LEFT_Z),
        stamina=100.0,
        distress=0.0,
        crying=False,
    )
    agents = {trespasser.agent_id: trespasser}

    security.step(current_tick=100, agents=agents)

    assert trespasser.distress >= 0.9
    assert trespasser.crying is True
    assert trespasser.stamina <= 0.0

    assert len(judiciary.cases) >= 1
    trespass_case = next(c for c in judiciary.cases.values() if c.accused_id == trespasser.agent_id)
    assert trespass_case.offense_type == "TRESPASS"

    alerts = [e for e in adapter.events if e[0] == "PALACE_TRESPASS_ALERT"]
    assert len(alerts) >= 1
    assert alerts[0][1]["agent_id"] == "intruder_shadow"


def test_palace_knight_battalion_deployment_and_patrols(engine: SimulationEngine) -> None:
    """Palace Knight Battalion spawns 24 guards with proper roles, waypoints, and positions."""
    knights = engine.palace_security.spawn_knight_battalion(engine.agents, count=24)
    assert len(knights) == 24
    assert len(engine.palace_security.knight_agent_ids) == 24

    roles_map = engine.palace_security.knight_roles
    wall_sentries = [k for k in knights if roles_map[k.agent_id] == "WALL_SENTRY"]
    courtyard_sentries = [k for k in knights if roles_map[k.agent_id] == "COURTYARD_SENTRY"]
    road_sentries = [k for k in knights if roles_map[k.agent_id] == "ROAD_CHECKPOINT"]
    rapid_response = [k for k in knights if roles_map[k.agent_id] == "RAPID_RESPONSE"]

    assert len(wall_sentries) == 4
    assert len(courtyard_sentries) == 4
    assert len(road_sentries) == 10
    assert len(rapid_response) == 6

    for k in knights:
        assert k.role == "PALACE_KNIGHT"
        assert k.pos.y == PALACE_CENTER_Y
        assert k.agent_id in engine.spatial_grid._agent_positions

    for _ in range(5):
        engine.step_tick()


def test_palace_security_and_navigation_harmony(tmp_path: Path) -> None:
    """Verifies Palace Knights profession, allow_palace_interior, and intercept escort."""
    engine = SimulationEngine(
        db_path=tmp_path / "civ_sec.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        adapter=MockWorldAdapter(),
        headless=True,
    )

    knights = engine.palace_security.spawn_knight_battalion(engine.agents, count=24)
    for k in knights:
        assert k.role == "PALACE_KNIGHT"
        assert k.profession == "KNIGHT"

    next_x, next_z, _ = engine.navigation.resolve_world_movement(
        current_x=20.0,
        current_z=20.0,
        target_x=25.0,
        target_z=25.0,
        allow_palace_interior=True,
    )
    assert math.hypot(next_x, next_z) < 90.0

    syl_x, syl_z, _ = engine.navigation.resolve_world_movement(
        current_x=1150.0,
        current_z=5.0,
        target_x=1150.0,
        target_z=10.0,
        allow_palace_interior=True,
    )
    assert abs(syl_x - 1150.0) < 2.0

    bld_test = engine.city_layout.buildings["bld_sylvanor_seed_01"]
    door_vec = engine.navigation.get_building_door_pos("bld_sylvanor_seed_01", bld_test)
    assert door_vec is not None
    dist_door_to_center = math.hypot(door_vec.x - bld_test.x, door_vec.z - bld_test.z)
    assert dist_door_to_center >= bld_test.footprint_radius + 1.0

    p_agent = engine.spawn_agent(
        race="HUMAN", gender="BOY", stage="ADULT", pos=Vec3(x=500.0, y=0.0, z=500.0)
    )
    engine.navigation.get_next_waypoint(
        p_agent.agent_id, p_agent.pos, Vec3(x=1000.0, y=0.0, z=1000.0)
    )
    assert p_agent.agent_id in engine.navigation._agent_path_cache
    engine.despawn_agent(p_agent.agent_id)
    assert p_agent.agent_id not in engine.navigation._agent_path_cache

    p_out = Vec3(x=1395.0, y=0.0, z=30.0)
    p_in = Vec3(x=1370.0, y=0.0, z=0.0)
    wp = engine.navigation.get_next_waypoint("test_cross_wall", p_out, p_in)
    assert wp != p_in

    out_x, out_z, _ = engine.navigation.resolve_world_movement(
        current_x=0.0,
        current_z=60.0,
        target_x=0.0,
        target_z=0.0,
        allow_palace_interior=False,
    )
    assert math.hypot(out_x, out_z) >= 90.0

    visitor = engine.spawn_agent(
        race="HUMAN", gender="BOY", stage="ADULT", pos=Vec3(x=0.0, y=32.0, z=36.0)
    )
    engine.palace_security.active_passes[visitor.agent_id] = PalacePass(
        pass_id="pass_vis_01",
        agent_id=visitor.agent_id,
        granted_by="WORLD_GODDESS",
        granted_tick=1,
        expires_tick=1000,
    )
    allow = engine.palace_security.is_whitelisted(
        visitor
    ) or engine.palace_security.has_active_pass(visitor.agent_id, 10)
    assert allow is True

    intruder = engine.spawn_agent(
        race="HUMAN", gender="BOY", stage="ADULT", pos=Vec3(x=0.0, y=32.0, z=50.0)
    )
    engine.palace_security._dispatch_intercept(intruder.agent_id)
    assigned_count = sum(
        1 for tid, _ in engine.palace_security.knight_targets.values() if tid == intruder.agent_id
    )
    assert assigned_count == 1

    engine.palace_security._dispatch_intercept(intruder.agent_id)
    assigned_count_2 = sum(
        1 for tid, _ in engine.palace_security.knight_targets.values() if tid == intruder.agent_id
    )
    assert assigned_count_2 == 1

    intruder.pos.x = 0.0
    intruder.pos.z = OUTER_BOUNDARY_RADIUS + 10.0
    engine.palace_security.reported_trespassers.add(intruder.agent_id)
    engine.palace_security._step_knights(engine.agents)

    active_targets = [tid for tid, _ in engine.palace_security.knight_targets.values()]
    assert intruder.agent_id not in active_targets
    assert intruder.agent_id not in engine.palace_security.reported_trespassers

    intruder2 = engine.spawn_agent(
        race="HUMAN", gender="BOY", stage="ADULT", pos=Vec3(x=0.0, y=32.0, z=91.5)
    )
    engine.palace_security._dispatch_intercept(intruder2.agent_id)
    kid = [
        k for k, (t, m) in engine.palace_security.knight_targets.items() if t == intruder2.agent_id
    ][0]
    k_agent = engine.agents[kid]
    k_agent.pos.x = 0.0
    k_agent.pos.z = 92.5
    engine.palace_security._step_knights(engine.agents)
    assert engine.palace_security.knight_targets[kid][1] == "ESCORT"
    assert intruder2.stamina == 0.0
    for _ in range(45):
        engine.palace_security._step_knights(engine.agents)
    assert kid not in engine.palace_security.knight_targets
    assert intruder2.pos.z >= 130.0

    guards_syl = engine.city_layout.spawn_city_guard_garrison(engine.agents, "sylvanor", count=10)
    g1 = guards_syl[0]
    engine.city_layout.step_patrols(tick=20, agents_dict=engine.agents)
    assert g1.yaw != 0.0 or g1.pos.x != 0.0


def test_building_obstacle_and_water_avoidance() -> None:
    nav = NavigationEngine(heightmap=None)
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

    nx, nz, _ = nav.resolve_world_movement(
        current_x=0.0,
        current_z=60.0,
        target_x=0.0,
        target_z=0.0,
        speed=20.0,
        dt=1.0,
    )
    dist_from_center = math.hypot(nx, nz)
    assert dist_from_center >= 50.0, f"Mortal penetrated building! Dist={dist_from_center}"


def test_vectorized_crowd_separation() -> None:
    nav = NavigationEngine(heightmap=None)
    grid = SpatialHashGrid(cell_size=16.0)

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

    init_dist = math.hypot(a1.pos.x - a2.pos.x, a1.pos.z - a2.pos.z)
    assert init_dist < 0.15

    for _ in range(5):
        nav.apply_crowd_separation(agents, grid, personal_space=0.85, repulsion_factor=0.5)
        grid.update_agent(a1.agent_id, a1.pos.x, a1.pos.z)
        grid.update_agent(a2.agent_id, a2.pos.x, a2.pos.z)

    sep_dist = math.hypot(a1.pos.x - a2.pos.x, a1.pos.z - a2.pos.z)
    assert sep_dist >= 0.80, f"Crowd separation failed! Final dist={sep_dist:.3f}m"


def test_god_presence_reaction() -> None:
    nav = NavigationEngine(heightmap=None)
    agent = AgentRecord(
        agent_id="mortal_devout",
        slot_idx=0,
        display_name="Brother Vael",
        dynasty_surname="Solaris",
        gender="BOY",
        race="HUMAN",
        pos=Vec3(x=1.0, y=24.0, z=0.0),
    )
    agent.personality = PersonalityVector(devotion=0.85)

    god_pos = Vec3(x=0.0, y=24.0, z=0.0)
    reacted = nav.apply_god_presence_reaction([agent], god_pos, presence_radius=6.0)
    assert reacted == 1
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

    activity_m, _ = nav.evaluate_utility_schedule(agent, tick=3150, weather="CLEAR")
    assert activity_m == "MORNING_PREP"

    activity_d, target_d = nav.evaluate_utility_schedule(agent, tick=5400, weather="CLEAR")
    assert activity_d == "STUDYING"
    assert target_d is not None and target_d.x == 180.0 and target_d.z == 180.0

    agent.personality = PersonalityVector(devotion=0.8)
    activity_e, _ = nav.evaluate_utility_schedule(agent, tick=8550, weather="CLEAR")
    assert activity_e == "EVENING_PRAYER"

    activity_n, _ = nav.evaluate_utility_schedule(agent, tick=10350, weather="CLEAR")
    assert activity_n == "SLEEPING"

    activity_storm, _ = nav.evaluate_utility_schedule(agent, tick=5400, weather="STORM")
    assert activity_storm == "SHELTERING"


def test_resolve_world_movement_uses_godot_minus_z_forward_yaw() -> None:
    nav = NavigationEngine(heightmap=None)

    _, _, yaw_north = nav.resolve_world_movement(0.0, 0.0, 0.0, -10.0, speed=2.0, dt=0.5)
    assert math.isclose(yaw_north, 0.0, abs_tol=1e-4)

    _, _, yaw_south = nav.resolve_world_movement(0.0, 0.0, 0.0, 10.0, speed=2.0, dt=0.5)
    assert math.isclose(abs(yaw_south), math.pi, abs_tol=1e-3)

    _, _, yaw_east = nav.resolve_world_movement(0.0, 0.0, 10.0, 0.0, speed=2.0, dt=0.5)
    assert math.isclose(yaw_east, -math.pi / 2.0, abs_tol=1e-3)

    _, _, yaw_west = nav.resolve_world_movement(0.0, 0.0, -10.0, 0.0, speed=2.0, dt=0.5)
    assert math.isclose(yaw_west, math.pi / 2.0, abs_tol=1e-3)

    nav.footprints.append(
        BuildingFootprint(
            name="Blocker",
            cx=0.0,
            cz=-2.0,
            radius=2.0,
            door_x=0.0,
            door_z=0.0,
        )
    )
    nx, nz, yaw_deflected = nav.resolve_world_movement(0.6, -0.5, 0.0, -5.0, speed=4.0, dt=0.5)
    expected_yaw = round(math.atan2(-(nx - 0.6), -(nz - (-0.5))), 4)
    assert math.isclose(yaw_deflected, expected_yaw, abs_tol=1e-4)


def test_apply_god_presence_reaction_faces_god_with_minus_z_yaw() -> None:
    nav = NavigationEngine(heightmap=None)
    agent = AgentRecord(
        agent_id="a1",
        slot_idx=0,
        race="HUMAN",
        gender="GIRL",
        stage="ADULT",
        display_name="Lyra",
        dynasty_surname="Vale",
        pos=Vec3(x=10.0, y=0.0, z=10.0),
    )
    affected = nav.apply_god_presence_reaction([agent], Vec3(x=10.0, y=0.0, z=6.0))
    assert affected == 1
    assert math.isclose(agent.yaw, 0.0, abs_tol=1e-4)

    agent2 = AgentRecord(
        agent_id="a2",
        slot_idx=1,
        race="ELF",
        gender="BOY",
        stage="ADULT",
        display_name="Theron",
        dynasty_surname="Oak",
        pos=Vec3(x=0.0, y=0.0, z=0.0),
    )
    nav.apply_god_presence_reaction([agent2], Vec3(x=3.0, y=0.0, z=4.0))
    assert math.isclose(agent2.yaw, round(math.atan2(-3.0, -4.0), 4), abs_tol=1e-4)


@pytest.mark.benchmark
@pytest.mark.slow
def test_spatial_hash_grid_benchmark() -> None:
    """Spawns 10,000 random coordinates and measures batch insert and query performance."""
    grid = SpatialHashGrid(cell_size=16.0)

    assert grid.get_parcel_id(0.0, 0.0) == "0_0"
    assert grid.get_parcel_id(16.5, -32.0) == "1_-2"

    num_agents = 10000
    np.random.seed(42)
    xs = np.random.uniform(-4000.0, 4000.0, size=num_agents).astype(np.float32)
    zs = np.random.uniform(-4000.0, 4000.0, size=num_agents).astype(np.float32)
    agent_ids = [f"agt_{i}" for i in range(num_agents)]

    grid.insert_batch(agent_ids, xs, zs)
    assert grid.count() == num_agents

    t1 = time.perf_counter()
    for i in range(50):
        neighbors = grid.query_radius(float(xs[i]), float(zs[i]), radius=140.0)
        assert len(neighbors) > 0

    query_duration_total_ms = (time.perf_counter() - t1) * 1000.0
    avg_query_ms = query_duration_total_ms / 50.0

    assert avg_query_ms < 0.25, f"Average query took {avg_query_ms:.4f} ms"
