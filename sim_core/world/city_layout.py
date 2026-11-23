"""
sim_core/world/city_layout.py
5 Equidistant Gated Racial Cities, 5 God-Mother Palaces, Modular Seed Housing & Shops,
City Gate Watches, and Open Ring 2 Frontier Wilderness.
Follows AGENTS.md Sprint 3 specification.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from sim_core.schemas import (
    AgentRecord,
    BuildingRecord,
    BuildingType,
    CityRecord,
    ParcelRecord,
    Vec3,
)

if TYPE_CHECKING:
    from sim_core.engine import SimulationEngine
    from sim_core.society.economy import WorldBank


# ------------------------------------------------------------------------------
# 5 Ring 1 City Specifications (r = 1,150m, 72° exact spacing)
# Anchored at terrain_metadata.json coordinates.
# ------------------------------------------------------------------------------
RING_1_CITY_SPECS: dict[str, dict[str, Any]] = {
    "sylvanor": {
        "city_id": "sylvanor",
        "name": "Sylvanor",
        "native_race": "ELF",
        "racial_style": "ELF",
        "center_x": 1150.0,
        "center_z": 0.0,
        "elevation_y": 28.0,
        "curtain_wall_radius": 240.0,
        "godmother_slot": "gm_elf",
        "description": "Elf emerald highland forest city",
    },
    "aurelia": {
        "city_id": "aurelia",
        "name": "Aurelia",
        "native_race": "HUMAN",
        "racial_style": "HUMAN",
        "center_x": 355.37,
        "center_z": 1093.71,
        "elevation_y": 18.0,
        "curtain_wall_radius": 240.0,
        "godmother_slot": "gm_human",
        "description": "Human sunlit temperate plains city",
    },
    "fenris_hold": {
        "city_id": "fenris_hold",
        "name": "Fenris Hold",
        "native_race": "BEASTHUMAN",
        "racial_style": "BEASTHUMAN",
        "center_x": -930.37,
        "center_z": 675.95,
        "elevation_y": 24.0,
        "curtain_wall_radius": 240.0,
        "godmother_slot": "gm_beasthuman",
        "description": "Beasthuman rugged timber steppes stronghold",
    },
    "malakor": {
        "city_id": "malakor",
        "name": "Malakor",
        "native_race": "DEMON",
        "racial_style": "DEMON",
        "center_x": -930.37,
        "center_z": -675.95,
        "elevation_y": 42.0,
        "curtain_wall_radius": 240.0,
        "godmother_slot": "gm_demon",
        "description": "Demon basalt crags and volcanic ashland metropolis",
    },
    "drakonis_spire": {
        "city_id": "drakonis_spire",
        "name": "Drakonis Spire",
        "native_race": "DRAGON",
        "racial_style": "DRAGON",
        "center_x": 355.37,
        "center_z": -1093.71,
        "elevation_y": 68.0,
        "curtain_wall_radius": 240.0,
        "godmother_slot": "gm_dragon",
        "description": "Dragon obsidian alpine peaks and volcanic aerie",
    },
}


class CityLayoutEngine:
    """
    Manages the 5 Ring 1 Gated Racial Cities:
    - Central God-Mother Palaces.
    - Street grid & seed buildings (Tier 1-3 houses, shops) on deeded 16x16m parcels.
    - Perimeter curtain walls (r = 240m) & 4 gates (1 Imperial Main Gate + 3 cardinal gates).
    - City Gate Watches & guard patrol shifts.
    - Verifies Ring 2 wilderness (r = 1,500m .. 3,300m) remains pristine.
    """

    def __init__(self, engine: SimulationEngine | None = None) -> None:
        self.engine = engine
        self.cities: dict[str, CityRecord] = {}
        self.buildings: dict[str, BuildingRecord] = {}
        self.guard_assignments: dict[str, list[str]] = {}  # city_id -> list[guard_agent_id]
        self._initialize_cities_and_buildings()

    def _initialize_cities_and_buildings(self) -> None:
        """Constructs all 5 Ring 1 city layouts, palaces, gates, and seed buildings."""
        for cid, spec in RING_1_CITY_SPECS.items():
            city = CityRecord(
                city_id=cid,
                name=spec["name"],
                native_race=spec["native_race"],
                racial_style=spec["racial_style"],
                center_x=spec["center_x"],
                center_z=spec["center_z"],
                elevation_y=spec["elevation_y"],
                curtain_wall_radius=spec["curtain_wall_radius"],
                godmother_slot=spec["godmother_slot"],
                buildings_count=0,
            )
            self.cities[cid] = city
            self.guard_assignments[cid] = []

            # 1. Central God-Mother Palace (r = 0..45m)
            self._create_godmother_palace(city)

            # 2. Perimeter Curtain Wall & 4 Gates (r = 240m)
            self._create_city_gates_and_walls(city)

            # 3. Organized Street Grid & Seed Buildings (r = 65m .. 200m)
            self._create_seed_buildings(city)

            city.buildings_count = len([b for b in self.buildings.values() if b.city_id == cid])

    def _get_elevation(self, x: float, z: float, default_y: float) -> float:
        """Looks up height from heightmap if available, otherwise returns default_y."""
        if self.engine and hasattr(self.engine, "heightmap") and self.engine.heightmap:
            try:
                return float(self.engine.heightmap.get_elevation(x, z))
            except Exception:
                return default_y
        return default_y

    def _register_parcel_deed(
        self,
        building: BuildingRecord,
        assessed_value: float,
        for_sale: bool,
        sale_price: float,
    ) -> None:
        """Registers a matching deeded 16x16m parcel into property_mgr."""
        if not self.engine or not hasattr(self.engine, "property_mgr"):
            return

        parcel_id = f"{building.parcel_x}_{building.parcel_z}"
        parcel = ParcelRecord(
            parcel_id=parcel_id,
            cx=building.parcel_x,
            cz=building.parcel_z,
            settlement_id=building.city_id,
            owner_id=building.owner_id,
            owner_type="AGENT" if building.owner_id else "UNCLAIMED",
            assessed_value=assessed_value,
            for_sale_price=sale_price if for_sale else None,
        )
        self.engine.property_mgr.register_parcel(parcel)

    def _create_godmother_palace(self, city: CityRecord) -> None:
        """Spawns the grand God-Mother Palace at the city center."""
        cx, cz = city.center_x, city.center_z
        elev_y = self._get_elevation(cx, cz, city.elevation_y)
        px = int(round(cx) // 16)
        pz = int(round(cz) // 16)

        bld_id = f"bld_{city.city_id}_palace"
        palace = BuildingRecord(
            building_id=bld_id,
            city_id=city.city_id,
            building_type="GODMOTHER_PALACE",
            racial_style=city.racial_style,
            x=round(cx, 2),
            y=round(elev_y, 2),
            z=round(cz, 2),
            rotation_y=0.0,
            parcel_x=px,
            parcel_z=pz,
            footprint_radius=35.0,
            owner_id=city.city_id,
            owner_name=f"{city.name} Seat of Divinity",
            for_sale=False,
            sale_price=0.0,
        )
        self.buildings[bld_id] = palace
        self._register_parcel_deed(palace, assessed_value=5000.0, for_sale=False, sale_price=0.0)

    def _create_city_gates_and_walls(self, city: CityRecord) -> None:
        """
        Creates 4 City Gates along perimeter curtain wall (r = 240m):
        - Imperial Main Gate facing directly toward (0, 0) along the Imperial Highway.
        - 3 cardinal/ring gates spaced at 90°, 180°, and 270°.
        """
        cx, cz = city.center_x, city.center_z
        r = city.curtain_wall_radius

        # Vector toward Imperial Acropolis (0, 0)
        main_gate_angle = math.atan2(-cz, -cx)

        gate_configs = [
            ("gate_imperial", main_gate_angle, "Imperial Main Gate"),
            ("gate_right", (main_gate_angle + math.pi * 0.5) % (2.0 * math.pi), "East Ring Gate"),
            ("gate_outer", (main_gate_angle + math.pi) % (2.0 * math.pi), "Hinterland Gate"),
            ("gate_left", (main_gate_angle + math.pi * 1.5) % (2.0 * math.pi), "West Ring Gate"),
        ]

        for suffix, angle, label in gate_configs:
            gx = cx + r * math.cos(angle)
            gz = cz + r * math.sin(angle)
            gy = self._get_elevation(gx, gz, city.elevation_y)
            px = int(round(gx) // 16)
            pz = int(round(gz) // 16)

            bld_id = f"bld_{city.city_id}_{suffix}"
            gate = BuildingRecord(
                building_id=bld_id,
                city_id=city.city_id,
                building_type="CITY_GATE",
                racial_style=city.racial_style,
                x=round(gx, 2),
                y=round(gy, 2),
                z=round(gz, 2),
                rotation_y=round(angle, 4),
                parcel_x=px,
                parcel_z=pz,
                footprint_radius=12.0,
                owner_id=city.city_id,
                owner_name=f"{city.name} {label}",
                for_sale=False,
                sale_price=0.0,
            )
            self.buildings[bld_id] = gate
            self._register_parcel_deed(gate, assessed_value=1200.0, for_sale=False, sale_price=0.0)

    def _create_seed_buildings(self, city: CityRecord) -> None:
        """
        Spawns 20 seed buildings per city across 4 modular archetypes (r = 65m .. 200m):
        - 7 HOUSE_T1_COTTAGE (starter/rental homes)
        - 6 HOUSE_T2_TOWNHOUSE (artisan family homes)
        - 3 HOUSE_T3_MANOR (wealthy elder/merchant estates)
        - 4 Commercial stalls/workshops (1 SHOP_MARKET, 2 SHOP_BLACKSMITH, 1 SHOP_TAVERN)
        Total = 20 seed buildings.
        ~65% initially owned by seed citizens (13 owned), ~35% listed for_sale = True (7 for sale).
        """
        cx, cz = city.center_x, city.center_z
        main_gate_angle = math.atan2(-cz, -cx)

        # 20 Building Archetypes & initial sale configurations
        building_templates: list[tuple[BuildingType, float, bool, str]] = [
            ("HOUSE_T1_COTTAGE", 180.0, False, "Cottage"),
            ("HOUSE_T1_COTTAGE", 180.0, True, "Starter Cottage"),
            ("HOUSE_T1_COTTAGE", 195.0, False, "Cottage"),
            ("HOUSE_T1_COTTAGE", 190.0, True, "Cozy Cottage"),
            ("HOUSE_T1_COTTAGE", 175.0, False, "Cottage"),
            ("HOUSE_T1_COTTAGE", 200.0, False, "Garden Cottage"),
            ("HOUSE_T1_COTTAGE", 185.0, True, "Market Cottage"),
            ("HOUSE_T2_TOWNHOUSE", 320.0, False, "Artisan Townhouse"),
            ("HOUSE_T2_TOWNHOUSE", 340.0, True, "Spacious Townhouse"),
            ("HOUSE_T2_TOWNHOUSE", 310.0, False, "Townhouse"),
            ("HOUSE_T2_TOWNHOUSE", 330.0, False, "Mason Townhouse"),
            ("HOUSE_T2_TOWNHOUSE", 350.0, True, "Grand Townhouse"),
            ("HOUSE_T2_TOWNHOUSE", 315.0, False, "Townhouse"),
            ("HOUSE_T3_MANOR", 580.0, False, "Elder Estate"),
            ("HOUSE_T3_MANOR", 620.0, True, "Merchant Manor"),
            ("HOUSE_T3_MANOR", 590.0, False, "Noble Manor"),
            ("SHOP_MARKET", 420.0, False, "City Provision Stalls"),
            ("SHOP_BLACKSMITH", 450.0, False, "Iron & Anvil Forge"),
            ("SHOP_BLACKSMITH", 440.0, True, "Artisan Smithy"),
            ("SHOP_TAVERN", 480.0, False, "The Wayfarer's Rest"),
        ]

        # Radial rings for street layout
        # Leave a 30° corridor clear toward main_gate_angle for Imperial Highway
        ring_radii = [80.0, 115.0, 150.0, 185.0]

        for idx, (btype, price, for_sale, desc) in enumerate(building_templates):
            ring_idx = idx % len(ring_radii)
            radius = ring_radii[ring_idx]

            # Distribute angularly around the city, skipping directly along main highway
            slot_in_ring = idx // len(ring_radii)
            angle_step = (2.0 * math.pi) / 6.0
            base_angle = (
                main_gate_angle + math.pi * 0.25 + slot_in_ring * angle_step + (ring_idx * 0.3)
            )
            angle = base_angle % (2.0 * math.pi)

            bx = cx + radius * math.cos(angle)
            bz = cz + radius * math.sin(angle)
            by = self._get_elevation(bx, bz, city.elevation_y)

            px = int(round(bx) // 16)
            pz = int(round(bz) // 16)

            # Rotation facing street / center
            rot_y = round((angle + math.pi) % (2.0 * math.pi), 4)

            bld_id = f"bld_{city.city_id}_seed_{idx + 1:02d}"
            owner_id = None if for_sale else f"citizen_{city.city_id}_{idx + 1:02d}"
            owner_name = None if for_sale else f"{city.name} {desc} Citizen"

            bld = BuildingRecord(
                building_id=bld_id,
                city_id=city.city_id,
                building_type=btype,
                racial_style=city.racial_style,
                x=round(bx, 2),
                y=round(by, 2),
                z=round(bz, 2),
                rotation_y=rot_y,
                parcel_x=px,
                parcel_z=pz,
                footprint_radius=(
                    8.0 if "COTTAGE" in btype else (11.0 if "TOWNHOUSE" in btype else 14.0)
                ),
                owner_id=owner_id,
                owner_name=owner_name,
                for_sale=for_sale,
                sale_price=price,
            )
            self.buildings[bld_id] = bld
            self._register_parcel_deed(
                bld,
                assessed_value=price * 0.9,
                for_sale=for_sale,
                sale_price=price,
            )

    def spawn_city_guard_garrison(
        self,
        agents_dict: dict[str, AgentRecord],
        city_id: str,
        count: int = 10,
    ) -> list[AgentRecord]:
        """
        Spawns native-race CITY_GUARD agents for the given city:
        - 4 stationed at the gates (Imperial Main Gate, East, Outer, West).
        - Remaining guards assigned to perimeter wall patrol shifts.
        """
        if city_id not in self.cities:
            return []

        city = self.cities[city_id]
        cx, cz = city.center_x, city.center_z
        r = city.curtain_wall_radius
        main_angle = math.atan2(-cz, -cx)

        gate_angles = [
            main_angle,
            (main_angle + math.pi * 0.5) % (2.0 * math.pi),
            (main_angle + math.pi) % (2.0 * math.pi),
            (main_angle + math.pi * 1.5) % (2.0 * math.pi),
        ]

        guards: list[AgentRecord] = []
        for i in range(count):
            if i < 4:
                # Gate Watch
                angle = gate_angles[i]
                gx = cx + r * math.cos(angle)
                gz = cz + r * math.sin(angle)
                title = f"{city.name} Gate Watch"
            else:
                # Perimeter Wall Patrol
                patrol_angle = (main_angle + (i * 0.6)) % (2.0 * math.pi)
                gx = cx + (r - 4.0) * math.cos(patrol_angle)
                gz = cz + (r - 4.0) * math.sin(patrol_angle)
                title = f"{city.name} Wall Sentinel"

            gy = self._get_elevation(gx, gz, city.elevation_y)
            agent_id = f"guard_{city.city_id}_{i + 1:02d}"

            if self.engine and hasattr(self.engine, "spawn_agent"):
                agent = self.engine.spawn_agent(
                    race=city.native_race,
                    gender="BOY" if i % 2 == 0 else "GIRL",
                    stage="ADULT",
                    pos=Vec3(x=round(gx, 2), y=round(gy, 2), z=round(gz, 2)),
                    role="CITY_GUARD",
                    title=title,
                    initial_credits=45.0,
                    agent_id=agent_id,
                )
                self.guard_assignments[city_id].append(agent.agent_id)
                guards.append(agent)

        return guards

    def buy_building(
        self,
        building_id: str,
        buyer_agent: AgentRecord,
        bank: WorldBank | None = None,
    ) -> tuple[bool, str]:
        """
        Executes real closed-loop purchase of a building and its deeded 16x16m parcel:
        - Debits credits from buyer_agent.
        - Updates BuildingRecord (owner_id, owner_name, for_sale=False).
        - Updates PropertyManager parcel deed.
        - Emits live BUILDING_UPDATE event over WebSocket bridge if connected.
        """
        if building_id not in self.buildings:
            return False, f"BUILDING_NOT_FOUND: {building_id}"

        bld = self.buildings[building_id]
        if not bld.for_sale:
            return False, f"NOT_FOR_SALE: Building {building_id} is already owned."

        if buyer_agent.credits < bld.sale_price:
            return (
                False,
                f"INSUFFICIENT_FUNDS: Buyer has {buyer_agent.credits:.1f} cr, "
                f"required {bld.sale_price:.1f} cr",
            )

        # Debit credits
        buyer_agent.credits -= bld.sale_price
        old_owner_id = bld.owner_id

        # Update building state
        bld.owner_id = buyer_agent.agent_id
        bld.owner_name = buyer_agent.display_name
        bld.for_sale = False

        # Update parcel deed in PropertyManager
        if self.engine and hasattr(self.engine, "property_mgr"):
            parcel_id = f"{bld.parcel_x}_{bld.parcel_z}"
            parcel = self.engine.property_mgr.parcels.get(parcel_id)
            if parcel:
                parcel.owner_id = buyer_agent.agent_id
                parcel.owner_type = "AGENT"
                parcel.for_sale_price = None

        # Emit live bridge update
        if self.engine and hasattr(self.engine, "adapter") and self.engine.adapter:
            try:
                self.engine.adapter.broadcast_event(
                    "BUILDING_UPDATE",
                    {
                        "type": "BUILDING_UPDATE",
                        "building": bld.model_dump(),
                    },
                )
            except Exception:
                pass

        msg = f"SUCCESS: Bought {building_id} for {bld.sale_price:.1f} cr from {old_owner_id}"
        return True, msg

    def step_patrols(self, tick: int, agents_dict: dict[str, AgentRecord]) -> None:
        """
        Steps guard patrol shifts: guards patrol their gate posts and curtain wall segments.
        Every 120 ticks, shifts oscillate between vantage posts.
        """
        if tick % 20 != 0:
            return

        phase = (tick // 120) % 2
        for cid, city in self.cities.items():
            cx, cz = city.center_x, city.center_z
            r = city.curtain_wall_radius
            main_angle = math.atan2(-cz, -cx)
            gate_angles = [
                main_angle,
                (main_angle + math.pi * 0.5) % (2.0 * math.pi),
                (main_angle + math.pi) % (2.0 * math.pi),
                (main_angle + math.pi * 1.5) % (2.0 * math.pi),
            ]

            guard_ids = self.guard_assignments.get(cid, [])
            for idx, gid in enumerate(guard_ids):
                agent = agents_dict.get(gid)
                if not agent or not agent.alive:
                    continue

                if idx < 4:
                    # Gate watch post with subtle vantage shift
                    g_angle = gate_angles[idx]
                    offset_angle = 0.05 if phase == 1 else -0.05
                    target_x = cx + r * math.cos(g_angle + offset_angle)
                    target_z = cz + r * math.sin(g_angle + offset_angle)
                else:
                    # Wall patrol
                    base_angle = (main_angle + (idx * 0.6)) % (2.0 * math.pi)
                    shift = 0.12 if phase == 1 else -0.12
                    target_x = cx + (r - 4.0) * math.cos(base_angle + shift)
                    target_z = cz + (r - 4.0) * math.sin(base_angle + shift)

                target_y = self._get_elevation(target_x, target_z, city.elevation_y)
                # Nudge agent smoothly toward post
                agent.pos.x += (target_x - agent.pos.x) * 0.15
                agent.pos.z += (target_z - agent.pos.z) * 0.15
                agent.pos.y = target_y

    def verify_ring_2_wilderness(self) -> tuple[bool, str]:
        """
        Confirms Ring 2 Frontier Wilderness Invariant:
        - Ring 2 (r = 1,500m .. 3,300m) is strictly wilderness with ZERO pre-built buildings.
        - No buildings exist outside Acropolis and outside 5 Ring 1 city footprints.
        """
        for bld in self.buildings.values():
            if bld.is_frontier:
                continue
            dist_origin = math.hypot(bld.x, bld.z)

            # Ring 2 check: 1500m <= r <= 3300m must be empty of pre-built structures
            if 1500.0 <= dist_origin <= 3300.0:
                msg = f"WILDERNESS_VIOLATION: {bld.building_id} in Ring 2 at {dist_origin:.1f}m"
                return False, msg

            # Must be either within Acropolis (r <= 360m) or within a city footprint (dist <= 280m)
            if dist_origin <= 360.0:
                continue

            # Check distance to each city center
            in_city_footprint = False
            for city in self.cities.values():
                d = math.hypot(bld.x - city.center_x, bld.z - city.center_z)
                if d <= 280.0:
                    in_city_footprint = True
                    break

            if not in_city_footprint:
                return (
                    False,
                    f"UNAUTHORIZED_SETTLEMENT: Building {bld.building_id} at ({bld.x}, {bld.z}) "
                    "is outside Acropolis and Ring 1 city footprints.",
                )

        return True, "RING_2_WILDERNESS_VERIFIED: Zero pre-built structures in Ring 2 wilderness."

    def get_building_sync_payload(self) -> dict[str, Any]:
        """Serializes full cities and buildings registry for WebSocket BUILDING_SYNC."""
        return {
            "type": "BUILDING_SYNC",
            "cities": [c.model_dump() for c in self.cities.values()],
            "buildings": [b.model_dump() for b in self.buildings.values()],
        }
