"""
sim_core/society/housing_market.py
Autonomous Housing Market, Closed-Loop Tier Upgrades, Probate/Escheatment,
and Emergent Ring 2 Frontier Pioneer Settlements.
Follows SOCIETY_AND_GOVERNANCE_SPEC.md and Gaia v4.0 Sprint 6.
"""

from __future__ import annotations

import math
import random
from typing import Any

from sim_core.schemas import AgentRecord, BuildingRecord, SettlementRecord, Vec3
from sim_core.society.economy import WorldBank


class HousingMarketEngine:
    """
    Manages autonomous city housing purchases, in-place tier upgrades,
    probate/escheatment of deceased estates, and Ring 2 pioneer frontier claims.
    Enforces strict double-entry credit conservation (0.000000 credit drift).
    """

    def __init__(self, engine: Any = None) -> None:
        self.engine = engine
        self.frontier_buildings: dict[str, BuildingRecord] = {}
        self.frontier_villages: dict[str, SettlementRecord] = {}
        self.pioneer_count: int = 0
        self.last_market_tick: int = 0
        self.last_pioneer_tick: int = 0
        self.rng = random.Random(42)

    def step_housing_market(
        self,
        agents: dict[str, AgentRecord],
        bank: WorldBank,
        current_tick: int,
    ) -> list[dict[str, Any]]:
        """
        Steps the autonomous housing market:
        1. Homeless/renting mortal adults purchase for-sale homes via closed-loop transfers.
        2. Homeowners upgrade cottages (T1 -> T2 -> T3) when having surplus credits.
        3. Probate & escheatment reallocates deceased homeowners' properties.
        """
        self.last_market_tick = current_tick
        events: list[dict[str, Any]] = []

        if not self.engine or not hasattr(self.engine, "city_layout"):
            return events

        city_blds = self.engine.city_layout.buildings

        # ---------------------------------------------------------------------
        # 1. Homeless/Renting Adult Purchases
        # ---------------------------------------------------------------------
        for agent in agents.values():
            if not agent.alive or agent.stage not in ("ADULT", "ELDER"):
                continue

            # Skip if already owns a valid home
            if agent.home_building_id and agent.home_building_id in city_blds:
                home_bld = city_blds[agent.home_building_id]
                if home_bld.owner_id == agent.agent_id:
                    continue

            # Candidate for home purchase
            # Find available for-sale residential buildings
            for_sale_blds = [
                b for b in city_blds.values()
                if b.for_sale and b.building_type in (
                    "HOUSE_T1_COTTAGE", "HOUSE_T2_TOWNHOUSE", "HOUSE_T3_MANOR"
                ) and agent.credits >= b.sale_price
            ]

            if not for_sale_blds:
                continue

            # Prefer native racial city if available, else cheapest
            buyer_race = agent.race

            def _score_building(b: BuildingRecord, target_race: str = buyer_race) -> float:
                pref_score = 0.0
                if b.racial_style == target_race:
                    pref_score -= 1000.0
                return pref_score + b.sale_price

            for_sale_blds.sort(key=_score_building)
            target_bld = for_sale_blds[0]
            price = target_bld.sale_price

            # Determine seller: previous owner agent if alive, else Bank as escrow
            seller: Any = bank
            if target_bld.owner_id and target_bld.owner_id in agents:
                prev_owner = agents[target_bld.owner_id]
                if prev_owner.alive:
                    seller = prev_owner

            ok, _ = bank.transfer_credits(
                sender=agent,
                receiver=seller,
                amount=price,
                memo=f"BUY_HOUSE_{target_bld.building_id}",
            )
            if not ok:
                continue

            # Transfer deed & update building
            target_bld.owner_id = agent.agent_id
            target_bld.owner_name = (
                f"{getattr(agent, 'display_name', 'Citizen')} "
                f"{getattr(agent, 'dynasty_surname', 'Founder')}"
            )
            target_bld.for_sale = False
            agent.home_building_id = target_bld.building_id

            # Update parcel deed if property_mgr active
            if hasattr(self.engine, "property_mgr") and self.engine.property_mgr:
                parcel_id = f"{target_bld.parcel_x}_{target_bld.parcel_z}"
                parcel = self.engine.property_mgr.parcels.get(parcel_id)
                if parcel:
                    parcel.owner_id = agent.agent_id
                    parcel.owner_type = "INDIVIDUAL"
                    parcel.for_sale_price = None

            # Broadcast live building update to Godot
            if hasattr(self.engine, "adapter") and self.engine.adapter:
                self.engine.adapter.sync_building_update(target_bld)

            events.append({
                "type": "HOUSE_PURCHASED",
                "building_id": target_bld.building_id,
                "buyer_id": agent.agent_id,
                "seller_id": getattr(seller, "agent_id", "BANK"),
                "price": price,
                "tick": current_tick,
            })

        # ---------------------------------------------------------------------
        # 2. In-Place Tier Upgrades (T1 -> T2 -> T3)
        # ---------------------------------------------------------------------
        for agent in agents.values():
            if not agent.alive or not agent.home_building_id:
                continue
            if agent.home_building_id not in city_blds:
                continue

            bld = city_blds[agent.home_building_id]
            if bld.owner_id != agent.agent_id:
                continue

            # Cottage to Townhouse upgrade (fee: 150 cr, requires >= 200 cr savings)
            if bld.building_type == "HOUSE_T1_COTTAGE" and agent.credits >= 200.0:
                fee = 150.0
                ok, _ = bank.transfer_credits(
                    sender=agent,
                    receiver=bank,
                    amount=fee,
                    memo=f"UPGRADE_T1_T2_{bld.building_id}",
                )
                if ok:
                    bld.building_type = "HOUSE_T2_TOWNHOUSE"
                    bld.footprint_radius = 11.0
                    bld.sale_price = 340.0
                    if hasattr(self.engine, "adapter") and self.engine.adapter:
                        self.engine.adapter.sync_building_update(bld)
                    events.append({
                        "type": "HOUSE_UPGRADED",
                        "building_id": bld.building_id,
                        "owner_id": agent.agent_id,
                        "new_tier": "HOUSE_T2_TOWNHOUSE",
                        "fee": fee,
                        "tick": current_tick,
                    })

            # Townhouse to Manor upgrade (fee: 280 cr, requires >= 360 cr savings)
            elif bld.building_type == "HOUSE_T2_TOWNHOUSE" and agent.credits >= 360.0:
                fee = 280.0
                ok, _ = bank.transfer_credits(
                    sender=agent,
                    receiver=bank,
                    amount=fee,
                    memo=f"UPGRADE_T2_T3_{bld.building_id}",
                )
                if ok:
                    bld.building_type = "HOUSE_T3_MANOR"
                    bld.footprint_radius = 14.0
                    bld.sale_price = 600.0
                    if hasattr(self.engine, "adapter") and self.engine.adapter:
                        self.engine.adapter.sync_building_update(bld)
                    events.append({
                        "type": "HOUSE_UPGRADED",
                        "building_id": bld.building_id,
                        "owner_id": agent.agent_id,
                        "new_tier": "HOUSE_T3_MANOR",
                        "fee": fee,
                        "tick": current_tick,
                    })

        # ---------------------------------------------------------------------
        # 3. Probate & Escheatment for Deceased Homeowners
        # ---------------------------------------------------------------------
        for bld in list(city_blds.values()):
            if not bld.owner_id or bld.owner_id == bld.city_id or bld.building_type in (
                "GODMOTHER_PALACE", "CITY_GATE", "WALL_SEGMENT"
            ):
                continue

            owner = agents.get(bld.owner_id)
            if owner and owner.alive:
                continue

            # Owner is dead or missing: execute probate cascade
            deceased = owner
            heir: AgentRecord | None = None

            if deceased:
                # 1. Living spouse
                if deceased.spouse_id and deceased.spouse_id in agents:
                    cand = agents[deceased.spouse_id]
                    if cand.alive:
                        heir = cand

                # 2. Living children
                if not heir:
                    children = [
                        a for a in agents.values()
                        if a.alive and deceased.agent_id in a.parent_ids
                    ]
                    if children:
                        adult_children = [c for c in children if c.stage in ("ADULT", "ELDER")]
                        heir = max(adult_children or children, key=lambda c: c.age_ticks)

            if heir:
                # Heir inherits property
                bld.owner_id = heir.agent_id
                bld.owner_name = (
                    f"{getattr(heir, 'display_name', 'Citizen')} "
                    f"{getattr(heir, 'dynasty_surname', 'Founder')}"
                )
                heir.home_building_id = bld.building_id
                events.append({
                    "type": "HOUSE_PROBATE_INHERITED",
                    "building_id": bld.building_id,
                    "heir_id": heir.agent_id,
                    "tick": current_tick,
                })
            else:
                # Escheatment: property returns to municipal market for sale
                bld.owner_id = None
                bld.owner_name = None
                bld.for_sale = True
                bld.sale_price = (
                    180.0 if "COTTAGE" in bld.building_type
                    else (320.0 if "TOWNHOUSE" in bld.building_type else 580.0)
                )
                events.append({
                    "type": "HOUSE_ESCHEATMENT_FOR_SALE",
                    "building_id": bld.building_id,
                    "sale_price": bld.sale_price,
                    "tick": current_tick,
                })

            if hasattr(self.engine, "adapter") and self.engine.adapter:
                self.engine.adapter.sync_building_update(bld)

        return events

    def step_frontier_pioneers(
        self,
        agents: dict[str, AgentRecord],
        bank: WorldBank,
        current_tick: int,
    ) -> list[BuildingRecord]:
        """
        Allows adventurous/ambitious mortals to claim 16x16m frontier parcels
        in Ring 2 wilderness (1500m <= r <= 3300m) on dry land (y >= 4.0m).
        When >= 3 frontier buildings cluster within 120m, registers an emergent VILLAGE.
        """
        self.last_pioneer_tick = current_tick
        spawned_buildings: list[BuildingRecord] = []

        if not self.engine or not hasattr(self.engine, "city_layout"):
            return spawned_buildings

        city_blds = self.engine.city_layout.buildings

        # Identify candidate pioneers: adults without homes with >= 120 cr
        candidates = [
            a for a in agents.values()
            if a.alive and a.stage in ("ADULT", "ELDER")
            and (not a.home_building_id or a.home_building_id not in city_blds)
            and a.credits >= 120.0
        ]

        if not candidates:
            return spawned_buildings

        # Pick 1-2 pioneers per step
        sample_count = min(len(candidates), 2)
        pioneers = self.rng.sample(candidates, sample_count)

        for pioneer in pioneers:
            construction_cost = 120.0

            # Find valid dry coordinate in Ring 2 wilderness (1500m .. 3200m)
            coord = self._find_frontier_plot()
            if not coord:
                continue

            bx, by, bz = coord

            # Closed-loop payment for frontier claim & building materials to World Bank
            ok, _ = bank.transfer_credits(
                sender=pioneer,
                receiver=bank,
                amount=construction_cost,
                memo="FRONTIER_PIONEER_CLAIM",
            )
            if not ok:
                continue

            self.pioneer_count += 1
            bld_id = f"bld_frontier_{self.pioneer_count:04d}"
            px = int(round(bx) // 16)
            pz = int(round(bz) // 16)
            rot_y = round(self.rng.uniform(0.0, 2.0 * math.pi), 4)

            pioneer_bld = BuildingRecord(
                building_id=bld_id,
                city_id="frontier",
                building_type="HOUSE_T1_COTTAGE",
                racial_style=pioneer.race,
                x=round(bx, 2),
                y=round(by, 2),
                z=round(bz, 2),
                rotation_y=rot_y,
                parcel_x=px,
                parcel_z=pz,
                footprint_radius=8.0,
                owner_id=pioneer.agent_id,
                owner_name=(
                    f"{getattr(pioneer, 'display_name', 'Citizen')} "
                    f"{getattr(pioneer, 'dynasty_surname', 'Founder')}"
                ),
                for_sale=False,
                sale_price=180.0,
                is_frontier=True,
            )

            city_blds[bld_id] = pioneer_bld
            self.frontier_buildings[bld_id] = pioneer_bld
            pioneer.home_building_id = bld_id

            # Register parcel deed
            if hasattr(self.engine, "property_mgr") and self.engine.property_mgr:
                self.engine.city_layout._register_parcel_deed(
                    pioneer_bld,
                    assessed_value=150.0,
                    for_sale=False,
                    sale_price=180.0,
                )

            # Broadcast live building creation
            if hasattr(self.engine, "adapter") and self.engine.adapter:
                self.engine.adapter.sync_building_update(pioneer_bld)

            spawned_buildings.append(pioneer_bld)

        # Check for emergent village clustering
        self._check_frontier_village_clustering(current_tick)

        return spawned_buildings

    def _find_frontier_plot(self) -> tuple[float, float, float] | None:
        """Finds a candidate dry land spot in Ring 2 wilderness (1500m <= r <= 3200m)."""
        city_blds = self.engine.city_layout.buildings if self.engine else {}
        heightmap = getattr(self.engine, "heightmap", None)

        for _ in range(30):
            r = self.rng.uniform(1550.0, 3150.0)
            ang = self.rng.uniform(0.0, 2.0 * math.pi)
            x = r * math.cos(ang)
            z = r * math.sin(ang)

            # Heightmap elevation lookup
            y = 12.0
            if (
                heightmap is not None
                and heightmap.data is not None
                and heightmap.data.max() > 0.0
            ):
                try:
                    y = float(heightmap.get_elevation(x, z))
                except Exception:
                    y = 12.0
                if y < 4.0:
                    continue
            else:
                y = 12.0

            # Ensure not colliding with existing buildings (>= 25m distance)
            collision = False
            for b in city_blds.values():
                dx = b.x - x
                dz = b.z - z
                if dx * dx + dz * dz < 25.0 * 25.0:
                    collision = True
                    break

            if not collision:
                return (x, y, z)

        return None

    def _check_frontier_village_clustering(self, current_tick: int) -> None:
        """
        Clusters unassigned frontier buildings:
        If >= 3 frontier buildings are within 120m of each other,
        forms an emergent SettlementRecord of tier VILLAGE.
        """
        unassigned = [b for b in self.frontier_buildings.values() if b.settlement_id is None]
        if len(unassigned) < 3:
            return

        cluster_dist_sq = 120.0 * 120.0

        for anchor in unassigned:
            cluster: list[BuildingRecord] = [anchor]
            for other in unassigned:
                if other.building_id == anchor.building_id:
                    continue
                dx = other.x - anchor.x
                dz = other.z - anchor.z
                if dx * dx + dz * dz <= cluster_dist_sq:
                    cluster.append(other)

            if len(cluster) >= 3:
                # Emergent Village formed!
                v_idx = len(self.frontier_villages) + 1
                v_id = f"village_frontier_{v_idx:02d}"
                owner_nm = cluster[0].owner_name
                founder_dynasty = owner_nm.split()[-1] if owner_nm else "Pioneer"
                v_name = f"{founder_dynasty} Frontier Settlement"

                cx = sum(b.x for b in cluster) / len(cluster)
                cy = sum(b.y for b in cluster) / len(cluster)
                cz = sum(b.z for b in cluster) / len(cluster)

                village = SettlementRecord(
                    settlement_id=v_id,
                    name=v_name,
                    tier="VILLAGE",
                    founder_id=cluster[0].owner_id or "founder",
                    center_pos=Vec3(x=round(cx, 2), y=round(cy, 2), z=round(cz, 2)),
                    treasury_credits=100.0,
                    founded_tick=current_tick,
                )

                self.frontier_villages[v_id] = village

                for b in cluster:
                    b.settlement_id = v_id
                    if hasattr(self.engine, "adapter") and self.engine.adapter:
                        self.engine.adapter.sync_building_update(b)

                # Register in engine border manager if available
                if hasattr(self.engine, "border_mgr") and self.engine.border_mgr:
                    try:
                        self.engine.border_mgr.register_settlement(village)
                    except Exception:
                        pass
                break
