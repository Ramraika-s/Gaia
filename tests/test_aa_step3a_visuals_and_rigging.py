"""
tests/test_aa_step3a_visuals_and_rigging.py
Stage 3A regression tests verifying Godot -Z forward yaw convention in NavigationEngine.
"""

from __future__ import annotations

import math

from sim_core.schemas import AgentRecord, Vec3
from sim_core.spatial.navigation import BuildingFootprint, NavigationEngine


def test_resolve_world_movement_uses_godot_minus_z_forward_yaw() -> None:
    nav = NavigationEngine(heightmap=None)

    # Moving straight -Z -> yaw == 0.0
    _, _, yaw_north = nav.resolve_world_movement(0.0, 0.0, 0.0, -10.0, speed=2.0, dt=0.5)
    assert math.isclose(yaw_north, 0.0, abs_tol=1e-4)

    # Moving straight +Z -> yaw == +/- pi
    _, _, yaw_south = nav.resolve_world_movement(0.0, 0.0, 0.0, 10.0, speed=2.0, dt=0.5)
    assert math.isclose(abs(yaw_south), math.pi, abs_tol=1e-3)

    # Moving straight +X -> atan2(-1, 0) == -pi/2
    _, _, yaw_east = nav.resolve_world_movement(0.0, 0.0, 10.0, 0.0, speed=2.0, dt=0.5)
    assert math.isclose(yaw_east, -math.pi / 2.0, abs_tol=1e-3)

    # Moving straight -X -> atan2(1, 0) == +pi/2
    _, _, yaw_west = nav.resolve_world_movement(0.0, 0.0, -10.0, 0.0, speed=2.0, dt=0.5)
    assert math.isclose(yaw_west, math.pi / 2.0, abs_tol=1e-3)

    # Deflection around obstacle updates yaw to match actual deflected step vector
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
    # God is directly to -Z of agent -> agent must turn to yaw == 0.0 (not pi)
    affected = nav.apply_god_presence_reaction([agent], Vec3(x=10.0, y=0.0, z=6.0))
    assert affected == 1
    assert math.isclose(agent.yaw, 0.0, abs_tol=1e-4)

    # God is diagonally at (+3, +4) from agent -> atan2(-3, -4)
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
