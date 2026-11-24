"""
sim_core/society/property.py
Deeded 16x16m chunk parcel management, sales, rentals,
deterministic probate cascades, and settlement/wilderness escheatment.
Follows SOCIETY_AND_GOVERNANCE_SPEC.md Section 5.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from sim_core.schemas import AgentRecord as AgentState
from sim_core.schemas import ParcelRecord

if TYPE_CHECKING:
    from sim_core.society.economy import WorldBank


def resolve_probate_heir(
    deceased: AgentState | Any,
    all_agents: Mapping[str, AgentState | Any],
) -> AgentState | Any | None:
    """
    Deterministic 4-tier heir resolution:
    1. Living Spouse
    2. Oldest Living Adult Child (or any living child if no adults)
    3. Living Parents (first available)
    4. Living Siblings (oldest available)
    5. None (Escheatment)
    """
    deceased_id = getattr(deceased, "agent_id", "")

    # 1. Check spouse
    spouse_id = getattr(deceased, "spouse_id", None)
    if spouse_id and spouse_id in all_agents:
        candidate = all_agents[spouse_id]
        if getattr(candidate, "alive", False):
            return candidate

    # 2. Check children
    living_children = [
        a
        for a in all_agents.values()
        if getattr(a, "alive", False) and deceased_id in getattr(a, "parent_ids", [])
    ]
    if living_children:
        adult_children = [
            c for c in living_children if getattr(c, "stage", "") in ("ADULT", "ELDER")
        ]
        if adult_children:
            return max(adult_children, key=lambda c: getattr(c, "age_ticks", 0))
        return max(living_children, key=lambda c: getattr(c, "age_ticks", 0))

    # 3. Check parents
    parent_ids = getattr(deceased, "parent_ids", [])
    if parent_ids:
        living_parents = [
            all_agents[pid]
            for pid in parent_ids
            if pid in all_agents and getattr(all_agents[pid], "alive", False)
        ]
        if living_parents:
            return living_parents[0]

    # 4. Check siblings
    if parent_ids:
        parent_set = set(parent_ids)
        living_siblings = [
            a
            for a in all_agents.values()
            if getattr(a, "alive", False)
            and getattr(a, "agent_id", "") != deceased_id
            and parent_set.intersection(getattr(a, "parent_ids", []))
        ]
        if living_siblings:
            return max(living_siblings, key=lambda s: getattr(s, "age_ticks", 0))

    return None


class PropertyManager:
    """Manages 16x16m deeded parcels, sales, leases, and probate."""

    def __init__(self, engine: Any = None) -> None:
        self.engine: Any = engine
        self.parcels: dict[str, ParcelRecord] = {}

    def register_parcel(self, parcel: ParcelRecord) -> None:
        """Registers a parcel into the property registry."""
        self.parcels[parcel.parcel_id] = parcel

    def get_parcel(self, cx: int, cz: int) -> ParcelRecord | None:
        """Look up parcel by chunk coordinates."""
        parcel_id = f"{cx}_{cz}"
        return self.parcels.get(parcel_id)

    def buy_parcel(
        self,
        buyer: AgentState | Any,
        parcel_id: str | None = None,
        price: float | None = None,
        seller: Any = None,
        bank: WorldBank | None = None,
    ) -> tuple[bool, str]:
        """Transfers ownership of a parcel to a buyer for credits."""
        # Handle flexible argument order if parcel_id passed as first arg
        if isinstance(buyer, str) and not isinstance(parcel_id, str) and parcel_id is not None:
            actual_pid = buyer
            actual_buyer = parcel_id
            actual_price = price
        else:
            actual_buyer = buyer
            actual_pid = parcel_id or ""
            actual_price = price

        if actual_pid not in self.parcels:
            return False, "PARCEL_NOT_FOUND"

        parcel = self.parcels[actual_pid]
        final_price = actual_price if actual_price is not None else (parcel.for_sale_price or 0.0)

        buyer_credits = getattr(actual_buyer, "credits", 0.0)
        if buyer_credits < final_price:
            msg = f"INSUFFICIENT_FUNDS: buyer has {buyer_credits:.2f}, price is {final_price:.2f}"
            return (False, msg)

        effective_bank = bank
        if effective_bank is None and self.engine is not None:
            effective_bank = getattr(self.engine, "bank", None)

        if effective_bank is None and seller is None:
            return False, "BANK_OR_SELLER_REQUIRED"

        old_owner_id = parcel.owner_id
        if effective_bank is not None:
            recipient = seller if seller is not None else effective_bank
            ok, reason = effective_bank.transfer_credits(
                sender=actual_buyer,
                receiver=recipient,
                amount=final_price,
                memo=f"BUY_PARCEL_{actual_pid}",
            )
            if not ok:
                return False, f"TRANSFER_FAILED: {reason}"
        else:
            if not isinstance(actual_buyer, str) and hasattr(actual_buyer, "credits"):
                actual_buyer.credits = getattr(actual_buyer, "credits", 0.0) - final_price
            if seller is not None and not isinstance(seller, str) and hasattr(seller, "credits"):
                seller.credits = getattr(seller, "credits", 0.0) + final_price

        parcel.owner_id = getattr(actual_buyer, "agent_id", str(actual_buyer))
        parcel.owner_type = "INDIVIDUAL"
        parcel.for_sale_price = None

        return True, f"PARCEL_PURCHASED: previously owned by {old_owner_id}"

    def execute_probate_and_escheatment(
        self,
        deceased: AgentState | Any,
        all_agents: Mapping[str, AgentState | Any],
        settlement_treasury_credit_fn: Any | None = None,
        bank: WorldBank | None = None,
        city_layout: Any = None,
        adapter: Any = None,
    ) -> list[tuple[str, str, str | None]]:
        """
        Executes deterministic probate cascade on all parcels owned by the deceased:
        1. Living spouse (spouse_id)
        2. Living children (preferring adult children)
        3. Living parents (parent_ids)
        4. Living siblings (sharing parent_ids)
        5. Escheatment:
           - Inside settlement border -> settlement treasury
           - Wilderness -> UNCLAIMED (owner_id = None, owner_type = "UNCLAIMED")
        Synchronizes both underlying parcels and occupying buildings in city_layout.
        Returns list of (parcel_id, disposition, new_owner_id).
        """
        results: list[tuple[str, str, str | None]] = []
        deceased_id = getattr(deceased, "agent_id", "")

        # Find all parcels owned by deceased
        owned_parcels = [p for p in self.parcels.values() if p.owner_id == deceased_id]

        # 1. Deterministic 4-tier heir resolution
        heir = resolve_probate_heir(deceased, all_agents)

        # Transfer deceased credits at most once
        if heir and getattr(deceased, "credits", 0.0) > 0.0:
            heir.credits += deceased.credits
            deceased.credits = 0.0

        credited_settlement = False
        # Apply probate or escheatment to each owned parcel
        for parcel in owned_parcels:
            if heir:
                parcel.owner_id = heir.agent_id
                parcel.owner_type = "INDIVIDUAL"
                parcel.for_sale_price = None
                results.append((parcel.parcel_id, "PROBATE_HEIR", heir.agent_id))
            else:
                # Escheatment
                if parcel.settlement_id:
                    parcel.owner_id = parcel.settlement_id
                    parcel.owner_type = "SETTLEMENT"
                    parcel.for_sale_price = parcel.assessed_value
                    if (
                        settlement_treasury_credit_fn
                        and getattr(deceased, "credits", 0.0) > 0.0
                        and not credited_settlement
                    ):
                        settlement_treasury_credit_fn(parcel.settlement_id, deceased.credits)
                        deceased.credits = 0.0
                        credited_settlement = True
                    results.append(
                        (parcel.parcel_id, "ESCHEATMENT_SETTLEMENT", parcel.settlement_id)
                    )
                else:
                    # Wilderness parcel reverts to UNCLAIMED
                    parcel.owner_id = None
                    parcel.owner_type = "UNCLAIMED"
                    parcel.for_sale_price = None
                    results.append((parcel.parcel_id, "ESCHEATMENT_WILDERNESS", "UNCLAIMED"))

        # Synchronize occupying BuildingRecord in city_layout if present
        if city_layout and hasattr(city_layout, "buildings"):
            owned_parcel_ids = {p.parcel_id for p in owned_parcels}
            for bld in city_layout.buildings.values():
                bld_parcel_id = f"{bld.parcel_x}_{bld.parcel_z}"
                matches_parcel = bld_parcel_id in owned_parcel_ids
                matches_owner = bld.owner_id == deceased_id
                if matches_parcel or matches_owner:
                    if heir:
                        bld.owner_id = heir.agent_id
                        bld.owner_name = (
                            f"{getattr(heir, 'display_name', 'Citizen')} "
                            f"{getattr(heir, 'dynasty_surname', 'Founder')}"
                        )
                        bld.for_sale = False
                        bld.sale_price = 0.0
                        heir.home_building_id = bld.building_id
                    else:
                        bld.owner_id = None
                        bld.owner_name = None
                        bld.for_sale = True
                        bld.sale_price = (
                            180.0
                            if "COTTAGE" in getattr(bld, "building_type", "")
                            else (
                                320.0
                                if "TOWNHOUSE" in getattr(bld, "building_type", "")
                                else 580.0
                            )
                        )
                    if adapter and hasattr(adapter, "sync_building_update"):
                        adapter.sync_building_update(bld)

        # Fallback for remaining credits if deceased had no heir and was not credited to settlement
        effective_bank = bank or (
            getattr(self.engine, "bank", None) if self.engine is not None else None
        )
        if not heir and getattr(deceased, "credits", 0.0) > 0.0 and effective_bank is not None:
            effective_bank.reserve_credits += deceased.credits
            deceased.credits = 0.0

        return results
