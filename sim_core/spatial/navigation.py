"""
sim_core/spatial/navigation.py
Spatial Awareness, Road/Doorway Pathfinding, Crowd Separation & Non-Robotic Schedules.
Follows Gaia v4.0 Sprint 5 specifications:
- Macro Road & Doorway Navigation: splines from world_roads.json, city gates, and building doorways.
- Building Footprint Avoidance: palaces, landmarks, city walls, and seed buildings.
- Micro Crowd Separation: vectorized soft 0.85m personal space repulsion via spatial hash grid.
- Non-Robotic 24-Hour Utility Scheduler: time-of-day, biological needs, weather interrupts.
- God Presence Awareness: reaction, facing, clearing path, bowing/wary stepback within 6.0m.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sim_core.config import TICKS_PER_GAME_DAY
from sim_core.schemas import AgentRecord, Season, Vec3

if TYPE_CHECKING:
    from sim_core.spatial.hash_grid import SpatialHashGrid
    from sim_core.spatial.heightmap import Heightmap

# Project root paths
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ROADS_JSON_PATH = REPO_ROOT / "godot_client" / "assets" / "terrain" / "world_roads.json"


class BuildingFootprint:
    """Represents an impassable circular or AABB building footprint with a doorway."""

    def __init__(
        self,
        name: str,
        cx: float,
        cz: float,
        radius: float,
        door_x: float,
        door_z: float,
        building_type: str = "BUILDING",
    ) -> None:
        self.name = name
        self.cx = cx
        self.cz = cz
        self.radius = radius
        self.door_x = door_x
        self.door_z = door_z
        self.building_type = building_type

    def is_inside(self, x: float, z: float, margin: float = 0.5) -> bool:
        dist_sq = (x - self.cx) ** 2 + (z - self.cz) ** 2
        return dist_sq < (self.radius + margin) ** 2

    def resolve_collision(self, x: float, z: float, margin: float = 0.5) -> tuple[float, float]:
        """Pushes position out to perimeter if inside footprint."""
        dx = x - self.cx
        dz = z - self.cz
        dist = math.hypot(dx, dz)
        min_dist = self.radius + margin
        if dist < 1e-4:
            # Directly on center; push outward in +Z
            return self.cx, self.cz + min_dist
        if dist < min_dist:
            scale = min_dist / dist
            return self.cx + dx * scale, self.cz + dz * scale
        return x, z


class CurtainWallObstacle:
    """Represents a circular city curtain wall with gate openings."""

    def __init__(
        self,
        city_id: str,
        cx: float,
        cz: float,
        radius: float = 240.0,
        wall_thickness: float = 8.0,
        gate_angles: list[float] | None = None,
        gate_width: float = 16.0,
    ) -> None:
        self.city_id = city_id
        self.cx = cx
        self.cz = cz
        self.radius = radius
        self.wall_thickness = wall_thickness
        self.gate_angles = gate_angles or [0.0, math.pi * 0.5, math.pi, math.pi * 1.5]
        self.gate_width = gate_width

    def is_blocked(self, x: float, z: float) -> bool:
        dx = x - self.cx
        dz = z - self.cz
        dist = math.hypot(dx, dz)
        r_inner = self.radius - (self.wall_thickness * 0.5)
        r_outer = self.radius + (self.wall_thickness * 0.5)
        if r_inner <= dist <= r_outer:
            # Check if within any gate passage
            angle = (math.atan2(dz, dx) + 2.0 * math.pi) % (2.0 * math.pi)
            for g_ang in self.gate_angles:
                norm_g = (g_ang + 2.0 * math.pi) % (2.0 * math.pi)
                ang_diff = abs(angle - norm_g)
                if ang_diff > math.pi:
                    ang_diff = 2.0 * math.pi - ang_diff
                arc_dist = ang_diff * self.radius
                if arc_dist < (self.gate_width * 0.5):
                    return False  # In gate gap
            return True
        return False

    def resolve_collision(
        self, x: float, z: float, prev_x: float, prev_z: float
    ) -> tuple[float, float]:
        if not self.is_blocked(x, z):
            return x, z
        dx = x - self.cx
        dz = z - self.cz
        dist = math.hypot(dx, dz)
        if dist < 1e-4:
            return x, z
        prev_dx = prev_x - self.cx
        prev_dz = prev_z - self.cz
        prev_dist = math.hypot(prev_dx, prev_dz)
        # Push back toward the side the agent came from
        if prev_dist < self.radius:
            target_r = self.radius - (self.wall_thickness * 0.5) - 0.5
        else:
            target_r = self.radius + (self.wall_thickness * 0.5) + 0.5
        return self.cx + (dx / dist) * target_r, self.cz + (dz / dist) * target_r


class NavigationEngine:
    """
    Core spatial pathfinding, obstacle avoidance, crowd separation,
    and 24-hour utility scheduling engine.
    """

    def __init__(self, heightmap: Heightmap | None = None) -> None:
        self.heightmap = heightmap
        self.footprints: list[BuildingFootprint] = []
        self.curtain_walls: list[CurtainWallObstacle] = []
        self.road_nodes: dict[str, Vec3] = {}
        self.road_edges: dict[str, list[str]] = {}

        self._load_road_network()
        self._register_default_landmarks()

    def _load_road_network(self) -> None:
        """Loads road nodes and edges from world_roads.json or procedural fallback."""
        data: dict[str, Any] = {}
        if ROADS_JSON_PATH.exists():
            try:
                with open(ROADS_JSON_PATH, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}

        # 1. Central Acropolis Hub
        self.road_nodes["acropolis_gate"] = Vec3(x=0.0, y=32.0, z=38.0)
        self.road_nodes["acropolis_center"] = Vec3(x=0.0, y=32.0, z=0.0)
        self._add_edge("acropolis_center", "acropolis_gate")

        # 2. Ring 0 Perimeter Nodes (r = 360m)
        r0 = 360.0
        r0_angles = [0.0, math.pi * 0.4, math.pi * 0.8, math.pi * 1.2, math.pi * 1.6]
        for i, ang in enumerate(r0_angles):
            nid = f"r0_node_{i}"
            nx = round(r0 * math.cos(ang), 2)
            nz = round(r0 * math.sin(ang), 2)
            self.road_nodes[nid] = Vec3(x=nx, y=24.0, z=nz)
            self._add_edge("acropolis_gate", nid)
            prev_nid = f"r0_node_{(i - 1) % len(r0_angles)}"
            if prev_nid in self.road_nodes:
                self._add_edge(nid, prev_nid)

        # 3. Radial Highways from world_roads.json
        radial_list = data.get("radial_highways", [])
        if radial_list:
            for hw in radial_list:
                cname = hw.get("city", "City").lower().replace(" ", "_")
                start_p = hw.get("start", {})
                end_p = hw.get("end", {})
                start_id = f"hw_start_{cname}"
                end_id = f"hw_end_{cname}"
                self.road_nodes[start_id] = Vec3(
                    x=float(start_p.get("x", 0.0)),
                    y=float(start_p.get("y", 24.0)),
                    z=float(start_p.get("z", 0.0)),
                )
                self.road_nodes[end_id] = Vec3(
                    x=float(end_p.get("x", 0.0)),
                    y=float(end_p.get("y", 24.0)),
                    z=float(end_p.get("z", 0.0)),
                )
                self._add_edge("acropolis_gate", start_id)
                self._add_edge(start_id, end_id)
        else:
            # Procedural fallback for 5 equidistant highways
            city_coords = [
                ("sylvanor", 1150.0, 0.0, 28.0),
                ("aurelia", 355.37, 1093.71, 18.0),
                ("fenris_hold", -930.37, 675.95, 24.0),
                ("malakor", -930.37, -675.95, 42.0),
                ("drakonis_spire", 355.37, -1093.71, 68.0),
            ]
            for cname, cx, cz, elev in city_coords:
                ang = math.atan2(cz, cx)
                start_id = f"hw_start_{cname}"
                end_id = f"hw_end_{cname}"
                self.road_nodes[start_id] = Vec3(
                    x=round(360.0 * math.cos(ang), 2),
                    y=24.0,
                    z=round(360.0 * math.sin(ang), 2),
                )
                self.road_nodes[end_id] = Vec3(
                    x=round(910.0 * math.cos(ang), 2),
                    y=elev,
                    z=round(910.0 * math.sin(ang), 2),
                )
                self._add_edge("acropolis_gate", start_id)
                self._add_edge(start_id, end_id)

    def _add_edge(self, node_a: str, node_b: str) -> None:
        self.road_edges.setdefault(node_a, []).append(node_b)
        self.road_edges.setdefault(node_b, []).append(node_a)

    def _register_default_landmarks(self) -> None:
        """Registers default footprints for palaces, institutions, and city walls."""
        # Grand Divine Palace (Acropolis inner sanctum: r = 95m)
        self.footprints.append(
            BuildingFootprint(
                name="Grand Divine Palace",
                cx=0.0,
                cz=0.0,
                radius=90.0,
                door_x=0.0,
                door_z=38.0,
                building_type="PALACE",
            )
        )

        # Central Basin Walk-In Landmarks
        landmarks = [
            ("World Library", 180.0, 180.0, 26.0, 175.0, 160.0),
            ("World Trade Centre", -180.0, 180.0, 28.0, -175.0, 160.0),
            ("Imperial Courthouse", -180.0, -180.0, 26.0, -175.0, -160.0),
            ("Grand Cathedral", 180.0, -180.0, 26.0, 175.0, -160.0),
        ]
        for name, lx, lz, rad, dx, dz in landmarks:
            self.footprints.append(
                BuildingFootprint(
                    name=name,
                    cx=lx,
                    cz=lz,
                    radius=rad,
                    door_x=dx,
                    door_z=dz,
                    building_type="LANDMARK",
                )
            )

        # 5 Ring 1 Cities: Palaces & Curtain Walls
        city_centers = [
            ("sylvanor", 1150.0, 0.0),
            ("aurelia", 355.37, 1093.71),
            ("fenris_hold", -930.37, 675.95),
            ("malakor", -930.37, -675.95),
            ("drakonis_spire", 355.37, -1093.71),
        ]
        for cid, ccx, ccz in city_centers:
            # City God-Mother Palace
            ang_to_origin = math.atan2(-ccz, -ccx)
            door_x = ccx + 35.0 * math.cos(ang_to_origin)
            door_z = ccz + 35.0 * math.sin(ang_to_origin)
            self.footprints.append(
                BuildingFootprint(
                    name=f"{cid}_palace",
                    cx=ccx,
                    cz=ccz,
                    radius=32.0,
                    door_x=door_x,
                    door_z=door_z,
                    building_type="GODMOTHER_PALACE",
                )
            )

            # Curtain Wall with 4 Gates
            self.curtain_walls.append(
                CurtainWallObstacle(
                    city_id=cid,
                    cx=ccx,
                    cz=ccz,
                    radius=240.0,
                    wall_thickness=10.0,
                    gate_angles=[
                        ang_to_origin,
                        (ang_to_origin + math.pi * 0.5) % (2.0 * math.pi),
                        (ang_to_origin + math.pi) % (2.0 * math.pi),
                        (ang_to_origin + math.pi * 1.5) % (2.0 * math.pi),
                    ],
                )
            )

    def register_building_footprint(
        self,
        name: str,
        cx: float,
        cz: float,
        radius: float,
        door_x: float,
        door_z: float,
        building_type: str = "BUILDING",
    ) -> None:
        """Dynamically registers modular seed buildings or player structures."""
        self.footprints.append(
            BuildingFootprint(name, cx, cz, radius, door_x, door_z, building_type)
        )

    # -------------------------------------------------------------------------
    # Pathfinding & Waypoint Routing
    # -------------------------------------------------------------------------

    def find_path(self, start: Vec3, destination: Vec3) -> list[Vec3]:
        """
        Finds intermediate road/corridor waypoints between start and destination.
        If distance is small (< 45m), returns direct line [destination].
        Otherwise finds nearest road entry node and destination road node.
        """
        dist = math.hypot(destination.x - start.x, destination.z - start.z)
        if dist <= 45.0:
            return [destination]

        nearest_start_node = self._find_nearest_road_node(start.x, start.z)
        nearest_dest_node = self._find_nearest_road_node(destination.x, destination.z)

        if not nearest_start_node or not nearest_dest_node:
            return [destination]

        if nearest_start_node == nearest_dest_node:
            return [self.road_nodes[nearest_start_node], destination]

        # Simple breadth-first search / greedy shortest road graph path
        path_nodes = self._bfs_road_path(nearest_start_node, nearest_dest_node)
        waypoints: list[Vec3] = [self.road_nodes[nid] for nid in path_nodes]
        waypoints.append(destination)
        return waypoints

    def _find_nearest_road_node(self, x: float, z: float) -> str | None:
        best_id: str | None = None
        best_dist = float("inf")
        for nid, node in self.road_nodes.items():
            d = (node.x - x) ** 2 + (node.z - z) ** 2
            if d < best_dist:
                best_dist = d
                best_id = nid
        return best_id

    def _bfs_road_path(self, start_id: str, goal_id: str) -> list[str]:
        queue: list[list[str]] = [[start_id]]
        visited: set[str] = {start_id}
        while queue:
            path = queue.pop(0)
            curr = path[-1]
            if curr == goal_id:
                return path
            for neighbor in self.road_edges.get(curr, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(path + [neighbor])
        return [start_id, goal_id]

    # -------------------------------------------------------------------------
    # Obstacle Avoidance & Collision Resolution
    # -------------------------------------------------------------------------

    def resolve_world_movement(
        self,
        current_x: float,
        current_z: float,
        target_x: float,
        target_z: float,
        speed: float = 2.0,
        dt: float = 0.5,
    ) -> tuple[float, float, float]:
        """
        Calculates safe next step toward (target_x, target_z), avoiding building
        interiors, city walls (except through gates), and ocean water (y < 0.0m).
        Returns: (next_x, next_z, next_yaw)
        """
        dx = target_x - current_x
        dz = target_z - current_z
        dist = math.hypot(dx, dz)

        if dist < 1e-4:
            return current_x, current_z, 0.0

        yaw = math.atan2(dx, dz)
        step = min(dist, speed * dt)
        step_x = current_x + (dx / dist) * step
        step_z = current_z + (dz / dist) * step

        # 1. Resolve Building Footprints
        for fp in self.footprints:
            if fp.is_inside(step_x, step_z):
                step_x, step_z = fp.resolve_collision(step_x, step_z)

        # 2. Resolve Curtain Walls
        for wall in self.curtain_walls:
            step_x, step_z = wall.resolve_collision(step_x, step_z, current_x, current_z)

        # 3. Resolve Ocean / Water (y >= 0.0m)
        if self.heightmap:
            try:
                elev = self.heightmap.get_elevation(step_x, step_z)
                if elev < 0.0:
                    # Push back toward previous valid coordinate
                    step_x = current_x
                    step_z = current_z
            except Exception:
                pass

        return round(step_x, 3), round(step_z, 3), round(yaw, 4)

    # -------------------------------------------------------------------------
    # Micro Crowd Separation (Vectorized Spatial Repulsion)
    # -------------------------------------------------------------------------

    def apply_crowd_separation(
        self,
        agents: list[AgentRecord],
        spatial_grid: SpatialHashGrid,
        personal_space: float = 0.85,
        repulsion_factor: float = 0.35,
    ) -> int:
        """
        Applies soft 0.85m personal space repulsion between nearby mortals using
        spatial hash grid so crowds part naturally and never stack on the same point.
        Returns the number of separating interactions applied.
        """
        interactions = 0
        min_dist_sq = personal_space**2

        # Fast lookup mapping
        agent_map: dict[str, AgentRecord] = {a.agent_id: a for a in agents}

        for agent in agents:
            nearby_ids = spatial_grid.get_nearby_ids(
                agent.pos.x, agent.pos.z, radius=personal_space * 1.5
            )
            for other_id in nearby_ids:
                if other_id == agent.agent_id:
                    continue
                other = agent_map.get(other_id)
                if not other:
                    continue

                dx = agent.pos.x - other.pos.x
                dz = agent.pos.z - other.pos.z
                dist_sq = dx * dx + dz * dz

                if 1e-6 < dist_sq < min_dist_sq:
                    dist = math.sqrt(dist_sq)
                    push = (personal_space - dist) * 0.5 * repulsion_factor
                    nx = dx / dist
                    nz = dz / dist

                    agent.pos.x += nx * push
                    agent.pos.z += nz * push
                    other.pos.x -= nx * push
                    other.pos.z -= nz * push

                    spatial_grid.update_agent(agent.agent_id, agent.pos.x, agent.pos.z)
                    spatial_grid.update_agent(other.agent_id, other.pos.x, other.pos.z)
                    interactions += 1

        return interactions

    # -------------------------------------------------------------------------
    # Non-Robotic 24-Hour Needs & Utility Scheduler
    # -------------------------------------------------------------------------

    def evaluate_utility_schedule(
        self,
        agent: AgentRecord,
        tick: int,
        season: Season = "SPRING",
        weather: str = "CLEAR",
        is_infant_crying_nearby: bool = False,
        home_pos: Vec3 | None = None,
        work_pos: Vec3 | None = None,
    ) -> tuple[str, Vec3 | None]:
        """
        Evaluates interruptible 24-hour schedule driven by simulation time-of-day,
        per-agent jitter, weather interrupts, and biological needs.
        Returns: (activity_state, target_position)
        """
        # Calculate time of day (0..24h) with deterministic agent jitter (+/- 20 mins)
        tick_in_day = tick % TICKS_PER_GAME_DAY
        base_hour = (tick_in_day / float(TICKS_PER_GAME_DAY)) * 24.0
        hash_val = hash(agent.agent_id) % 100
        jitter_hours = (hash_val - 50) * 0.007  # +/- 0.35 hours (~20 mins)
        hour = (base_hour + jitter_hours) % 24.0

        # Interrupt 1: Inclement Weather (RAIN, STORM, SNOW, ASH -> seek shelter)
        if weather in ("RAIN", "STORM", "SNOW", "ASH"):
            shelter_target = home_pos or self.road_nodes.get("acropolis_gate")
            return "SHELTERING", shelter_target

        # Interrupt 2: Distressed / Crying Infant Interrupt
        if is_infant_crying_nearby:
            return "COMFORT_CHILD", agent.pos

        # Interrupt 3: Critical Biological Needs
        if agent.hunger < 25.0:
            return "EATING", home_pos or work_pos or agent.pos
        if agent.fatigue > 0.85 and hour < 21.0 and hour > 6.0:
            return "RESTING", home_pos or agent.pos
        if agent.hygiene < 0.35:
            return "GROOMING", home_pos or agent.pos

        # Normal 24-Hour Day Phases:
        # 1. Morning (06:00 - 08:30): Hygiene, grooming, breakfast, exit home
        if 6.0 <= hour < 8.5:
            target = home_pos or agent.pos
            return "MORNING_PREP", target

        # 2. Day (08:30 - 17:30): Professional work, study, market, or patrol
        if 8.5 <= hour < 17.5:
            prof = agent.profession
            if prof in ("KNIGHT", "CITY_GUARD", "PALACE_KNIGHT"):
                return "PATROLLING", work_pos or self.road_nodes.get("acropolis_gate")
            elif prof == "SCHOLAR":
                return "STUDYING", Vec3(x=180.0, y=24.0, z=180.0)  # Library
            elif prof == "MERCHANT":
                return "TRADING", Vec3(x=-180.0, y=24.0, z=180.0)  # WTC
            elif prof == "CLERIC":
                return "PRAYING", Vec3(x=180.0, y=24.0, z=-180.0)  # Cathedral
            else:
                return "WORKING", work_pos or agent.pos

        # 3. Evening (17:30 - 21:00): Socializing in plaza/tavern or altar prayer
        if 17.5 <= hour < 21.0:
            devotion = agent.personality.devotion if agent.personality else 0.5
            if devotion >= 0.65:
                return "EVENING_PRAYER", Vec3(x=180.0, y=24.0, z=-180.0)
            return "SOCIALIZING", work_pos or agent.pos

        # 4. Night (21:00 - 06:00): Sleep at home (Guards and night demons patrol)
        prof = agent.profession
        if prof in ("KNIGHT", "CITY_GUARD", "PALACE_KNIGHT") or (
            agent.race == "DEMON" and hash_val < 30
        ):
            return "NIGHT_PATROL", work_pos or self.road_nodes.get("acropolis_gate")

        return "SLEEPING", home_pos or agent.pos

    # -------------------------------------------------------------------------
    # God Presence Awareness
    # -------------------------------------------------------------------------

    def apply_god_presence_reaction(
        self,
        agents: list[AgentRecord],
        god_pos: Vec3,
        presence_radius: float = 6.0,
    ) -> int:
        """
        When God Avatar is within 6.0m of mortals:
        - Mortals turn to face God Avatar.
        - Part smoothly to clear a path.
        - Bow/kneel if devout (devotion >= 0.55).
        - Step back cautiously if hostile / low-trust.
        Returns number of affected mortals.
        """
        affected = 0
        r_sq = presence_radius**2

        for agent in agents:
            dx = god_pos.x - agent.pos.x
            dz = god_pos.z - agent.pos.z
            d_sq = dx * dx + dz * dz

            if d_sq <= r_sq:
                dist = math.sqrt(max(1e-4, d_sq))
                # 1. Turn to face God Avatar
                agent.yaw = round(math.atan2(dx, dz), 4)

                # 2. Smoothly step aside to clear personal path (min 1.2m radius)
                if dist < 1.4:
                    push_away = (1.4 - dist) * 0.5
                    agent.pos.x -= (dx / dist) * push_away
                    agent.pos.z -= (dz / dist) * push_away

                # 3. Attitude response
                devotion = agent.personality.devotion if agent.personality else 0.5
                trust = agent.personality.out_group_trust if agent.personality else 0.5

                if devotion >= 0.55:
                    agent.activity_state = "BOWING"
                elif trust < 0.35:
                    agent.activity_state = "WARY_STEPBACK"
                else:
                    agent.activity_state = "REVERENT_IDLE"

                affected += 1

        return affected
