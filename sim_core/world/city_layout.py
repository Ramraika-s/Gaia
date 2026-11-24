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
        self._register_city_polities_and_borders()

    def _register_city_polities_and_borders(self) -> None:
        """Registers the 5 Ring 1 cities as CITY-tier polities and registers borders."""
        if not self.engine:
            return

        pol_engine = getattr(self.engine, "political_engine", None)
        border_mgr = getattr(self.engine, "border_mgr", None)

        from sim_core.society.politics import Polity

        for cid, city in self.cities.items():
            cx_p = int(round(city.center_x) // 16)
            cz_p = int(round(city.center_z) // 16)
            # 7x7 parcel grid (49 parcels) centered at city center meets
            # TIER_THRESHOLDS["CITY"] >= 48
            city_parcels = {
                f"{cx_p + dx}_{cz_p + dz}" for dx in range(-3, 4) for dz in range(-3, 4)
            }
            for b in self.buildings.values():
                if b.city_id == cid:
                    city_parcels.add(f"{b.parcel_x}_{b.parcel_z}")

            if pol_engine and cid not in pol_engine.polities:
                polity = Polity(
                    settlement_id=cid,
                    name=city.name,
                    tier="CITY",
                    regime_type="ELECTED" if cid in ("sylvanor", "aurelia") else "KING",
                    treasury_credits=2000.0,
                )
                polity.border_parcels.update(city_parcels)
                pol_engine.register_polity(polity)

            if border_mgr:
                border_mgr.register_settlement_border(cid, list(city_parcels))

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
                rotation_y=round((math.pi * 0.5) - angle, 4),
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
        Spawns 44 non-overlapping seed buildings per city arranged in 4 quadrants
        around 4 unobstructed 24m+ cross-axis boulevards (clearing >= 16° around
        every gate axis, r = 68m .. 196m):
        - 16 HOUSE_T1_COTTAGE (starter/rental homes)
        - 14 HOUSE_T2_TOWNHOUSE (artisan family homes)
        -  4 HOUSE_T3_MANOR (wealthy elder/merchant estates)
        - 10 Commercial shops (4 SHOP_MARKET, 4 SHOP_BLACKSMITH, 2 SHOP_TAVERN)
        Total = 44 seed buildings (~66% owned, ~34% for_sale).
        """
        cx, cz = city.center_x, city.center_z
        main_gate_angle = math.atan2(-cz, -cx)

        # 11-slot quadrant layout (angles in degrees inside [16°, 74°] of each 90° quadrant)
        # (radius, quad_offset_deg, face_mode, btype, price, for_sale, desc)
        # face_mode: "inward" -> faces center/inner plaza; "outward" -> faces outer mid street;
        #            "boulevard_ccw" / "boulevard_cw" -> faces nearest cross-axis boulevard
        quad_slots_even: list[tuple[float, float, str, BuildingType, float, bool, str]] = [
            (68.0, 24.0, "inward", "SHOP_MARKET", 420.0, False, "Market Stall"),
            (86.0, 45.0, "inward", "SHOP_TAVERN", 480.0, False, "Wayfarer's Rest"),
            (68.0, 66.0, "inward", "HOUSE_T2_TOWNHOUSE", 320.0, False, "Plaza Townhouse"),
            (116.0, 20.0, "boulevard_ccw", "HOUSE_T1_COTTAGE", 180.0, False, "Boulevard Cottage"),
            (132.0, 37.0, "outward", "HOUSE_T2_TOWNHOUSE", 330.0, True, "Artisan Townhouse"),
            (132.0, 53.0, "outward", "HOUSE_T1_COTTAGE", 190.0, True, "Corner Cottage"),
            (116.0, 70.0, "boulevard_cw", "SHOP_BLACKSMITH", 440.0, False, "Forge Workshop"),
            (174.0, 20.0, "inward", "HOUSE_T1_COTTAGE", 175.0, False, "Gatehouse Cottage"),
            (196.0, 37.0, "inward", "HOUSE_T3_MANOR", 590.0, False, "Elder Manor"),
            (196.0, 53.0, "inward", "HOUSE_T1_COTTAGE", 185.0, True, "Garden Cottage"),
            (174.0, 70.0, "inward", "HOUSE_T2_TOWNHOUSE", 315.0, False, "Outer Townhouse"),
        ]
        quad_slots_odd: list[tuple[float, float, str, BuildingType, float, bool, str]] = [
            (68.0, 24.0, "inward", "SHOP_MARKET", 420.0, False, "Market Stall"),
            (86.0, 45.0, "inward", "SHOP_BLACKSMITH", 450.0, True, "Artisan Smithy"),
            (68.0, 66.0, "inward", "HOUSE_T2_TOWNHOUSE", 320.0, False, "Plaza Townhouse"),
            (116.0, 20.0, "boulevard_ccw", "HOUSE_T1_COTTAGE", 180.0, False, "Boulevard Cottage"),
            (132.0, 37.0, "outward", "HOUSE_T2_TOWNHOUSE", 330.0, True, "Artisan Townhouse"),
            (132.0, 53.0, "outward", "HOUSE_T1_COTTAGE", 190.0, True, "Corner Cottage"),
            (116.0, 70.0, "boulevard_cw", "HOUSE_T2_TOWNHOUSE", 340.0, False, "Guild Townhouse"),
            (174.0, 20.0, "inward", "HOUSE_T1_COTTAGE", 175.0, False, "Gatehouse Cottage"),
            (196.0, 37.0, "inward", "HOUSE_T3_MANOR", 590.0, False, "Elder Manor"),
            (196.0, 53.0, "inward", "HOUSE_T1_COTTAGE", 185.0, True, "Garden Cottage"),
            (174.0, 70.0, "inward", "HOUSE_T2_TOWNHOUSE", 315.0, False, "Outer Townhouse"),
        ]

        placed_footprints: list[tuple[float, float, float]] = []
        used_parcels: set[tuple[int, int]] = set()
        idx = 0

        for q in range(4):
            quad_base_angle = main_gate_angle + q * (math.pi * 0.5)
            slots = quad_slots_even if (q % 2 == 0) else quad_slots_odd
            for slot_i, (radius, deg_off, face_mode, btype, price, for_sale, desc) in enumerate(
                slots
            ):
                if q == 3 and slot_i == 8:
                    for_sale = True
                    price = 620.0
                    desc = "Merchant Manor"

                idx += 1
                angle = (quad_base_angle + math.radians(deg_off)) % (2.0 * math.pi)
                bx = cx + radius * math.cos(angle)
                bz = cz + radius * math.sin(angle)
                by = self._get_elevation(bx, bz, city.elevation_y)

                px = int(round(bx) // 16)
                pz = int(round(bz) // 16)

                if face_mode == "inward":
                    face_angle = angle + math.pi
                elif face_mode == "boulevard_ccw":
                    # Face perpendicular toward quad_base_angle axis
                    face_angle = quad_base_angle - (math.pi * 0.5)
                elif face_mode == "boulevard_cw":
                    # Face perpendicular toward next quadrant's boulevard axis
                    face_angle = quad_base_angle + math.pi
                else:
                    face_angle = angle

                # Local +Z faces (sin(rot_y), cos(rot_y)) = (cos(face_angle), sin(face_angle))
                rot_y = round(((math.pi * 0.5) - face_angle) % (2.0 * math.pi), 4)

                fp_radius = 8.0 if "COTTAGE" in btype else (11.0 if "TOWNHOUSE" in btype else 14.0)
                for ox, oz, orad in placed_footprints:
                    dist_pair = math.hypot(bx - ox, bz - oz)
                    assert (
                        dist_pair >= fp_radius + orad + 2.5
                    ), f"Overlap in {city.city_id}: {dist_pair:.2f} < {fp_radius + orad + 2.5}"
                assert (px, pz) not in used_parcels, (
                    f"Duplicate parcel {(px, pz)} in {city.city_id}"
                )
                placed_footprints.append((bx, bz, fp_radius))
                used_parcels.add((px, pz))

                bld_id = f"bld_{city.city_id}_seed_{idx:02d}"
                owner_id = None if for_sale else f"citizen_{city.city_id}_{idx:02d}"
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
                    footprint_radius=fp_radius,
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

                # Register building footprint in navigation engine with doorway along Local +Z
                door_dist = bld.footprint_radius + 1.5
                door_x = round(bld.x + door_dist * math.sin(bld.rotation_y), 2)
                door_z = round(bld.z + door_dist * math.cos(bld.rotation_y), 2)
                if self.engine and hasattr(self.engine, "navigation") and self.engine.navigation:
                    self.engine.navigation.register_building_footprint(
                        name=bld.building_id,
                        cx=bld.x,
                        cz=bld.z,
                        radius=bld.footprint_radius,
                        door_x=door_x,
                        door_z=door_z,
                        building_type=bld.building_type,
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
                    settlement_id=city_id,
                )
                self.guard_assignments[city_id].append(agent.agent_id)
                guards.append(agent)

        return guards

    def rebuild_guard_roster(self, agents_registry: dict[str, AgentRecord]) -> None:
        """Reconstructs city guard assignments across all 5 Ring 1 cities from living agents."""
        for cid in self.cities:
            self.guard_assignments[cid] = []

        for agent in agents_registry.values():
            if not agent.alive or agent.role != "CITY_GUARD":
                continue

            # Determine assigned city
            cid = agent.settlement_id
            if not cid or cid not in self.cities:
                # Fall back to parsing guard_<city_id>_* or nearest city center
                if agent.agent_id.startswith("guard_"):
                    parts = agent.agent_id.split("_")
                    if len(parts) >= 2:
                        potential_cid = "_".join(parts[1:-1]) if len(parts) > 2 else parts[1]
                        if potential_cid in self.cities:
                            cid = potential_cid
                if not cid or cid not in self.cities:
                    best_dist = float("inf")
                    for c_key, c_val in self.cities.items():
                        dx = agent.pos.x - c_val.center_x
                        dz = agent.pos.z - c_val.center_z
                        d = dx * dx + dz * dz
                        if d < best_dist:
                            best_dist = d
                            cid = c_key

            if cid and cid in self.cities:
                if agent.agent_id not in self.guard_assignments[cid]:
                    self.guard_assignments[cid].append(agent.agent_id)

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

        old_owner_id = bld.owner_id
        active_bank = bank
        if active_bank is None and self.engine and hasattr(self.engine, "bank"):
            active_bank = self.engine.bank

        if active_bank is not None:
            seller: Any = active_bank
            if old_owner_id and self.engine and old_owner_id in self.engine.agents:
                prev_owner = self.engine.agents[old_owner_id]
                if prev_owner.alive:
                    seller = prev_owner
            ok, reason = active_bank.transfer_credits(
                sender=buyer_agent,
                receiver=seller,
                amount=bld.sale_price,
                memo=f"BUY_BUILDING_{building_id}",
            )
            if not ok:
                return False, f"TRANSFER_FAILED: {reason}"
        else:
            return False, "BANK_OR_SELLER_REQUIRED"

        # Update building state
        bld.owner_id = buyer_agent.agent_id
        bld.owner_name = buyer_agent.display_name
        bld.for_sale = False

        if bld.building_type.startswith("HOUSE_"):
            buyer_agent.home_building_id = building_id

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
            except Exception as ex:
                if self.engine and hasattr(self.engine, "healer") and self.engine.healer:
                    self.engine.healer.handle(
                        "WS_BRIDGE_DROP",
                        day=getattr(self.engine, "current_day", 1),
                        tick=getattr(self.engine, "current_tick", 0),
                        context={"error": str(ex), "action": "BUILDING_UPDATE_BROADCAST"},
                    )

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
                dx = target_x - agent.pos.x
                dz = target_z - agent.pos.z
                if abs(dx) > 1e-4 or abs(dz) > 1e-4:
                    agent.yaw = round(math.atan2(-dx, -dz), 4)
                # Nudge agent smoothly toward post
                agent.pos.x += dx * 0.15
                agent.pos.z += dz * 0.15
                agent.pos.y = target_y

                if self.engine:
                    if hasattr(self.engine, "spatial_grid") and self.engine.spatial_grid:
                        self.engine.spatial_grid.update_agent(gid, agent.pos.x, agent.pos.z)
                    if hasattr(self.engine, "adapter") and self.engine.adapter:
                        self.engine.adapter.update_agent_position(
                            slot_idx=agent.slot_idx,
                            x=agent.pos.x,
                            y=agent.pos.y,
                            z=agent.pos.z,
                            yaw=agent.yaw,
                        )

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
