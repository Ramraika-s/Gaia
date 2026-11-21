"""
sim_core/society/property.py
Deeded 16x16m chunk parcel management, sales, rentals,
deterministic probate cascades, and settlement/wilderness escheatment.
Follows SOCIETY_AND_GOVERNANCE_SPEC.md Section 5.
"""

from __future__ import annotations

from typing import Any

from sim_core.schemas import AgentRecord as AgentState
from sim_core.schemas import ParcelRecord


class PropertyManager:
    """Manages 16x16m deeded parcels, sales, leases, and probate."""

    def __init__(self):
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
        parcel_id: str,
        price: float,
    ) -> tuple[bool, str]:
        """Transfers ownership of a parcel to a buyer for credits."""
        if parcel_id not in self.parcels:
            return False, "PARCEL_NOT_FOUND"

        parcel = self.parcels[parcel_id]
        if buyer.credits < price:
            return False, f"INSUFFICIENT_FUNDS: buyer has {buyer.credits:.2f}, price is {price:.2f}"

        # Deduct credits
        buyer.credits -= price

        # If previous owner was an agent, credit them
        old_owner_id = parcel.owner_id
        parcel.owner_id = getattr(buyer, "agent_id", str(buyer))
        parcel.owner_type = "INDIVIDUAL"
        parcel.for_sale_price = None

        return True, f"PARCEL_PURCHASED: previously owned by {old_owner_id}"

    def execute_probate_and_escheatment(
        self,
        deceased: AgentState,
        all_agents: dict[str, AgentState],
        settlement_treasury_credit_fn: Any | None = None,
    ) -> list[tuple[str, str, str]]:
        """
        Executes deterministic probate cascade on all parcels owned by the deceased:
        1. Living spouse (spouse_id)
        2. Living children (preferring adult children)
        3. Living parents (parent_ids)
        4. Living siblings (sharing parent_ids)
        5. Escheatment:
           - Inside settlement border -> settlement treasury
           - Wilderness -> UNCLAIMED (owner_id = None, owner_type = "UNCLAIMED")
        Returns list of (parcel_id, disposition, new_owner_id).
        """
        results: list[tuple[str, str, str]] = []
        deceased_id = deceased.agent_id

        # Find all parcels owned by deceased
        owned_parcels = [p for p in self.parcels.values() if p.owner_id == deceased_id]

        # 1. Find heir if available
        heir: AgentState | None = None

        # Check spouse
        if deceased.spouse_id and deceased.spouse_id in all_agents:
            candidate = all_agents[deceased.spouse_id]
            if candidate.alive:
                heir = candidate

        # Check children
        if not heir:
            living_children = [
                a for a in all_agents.values()
                if a.alive and deceased_id in a.parent_ids
            ]
            if living_children:
                # Prefer adult children, else oldest
                adult_children = [c for c in living_children if c.stage in ("ADULT", "ELDER")]
                if adult_children:
                    heir = max(adult_children, key=lambda c: c.age_ticks)
                else:
                    heir = max(living_children, key=lambda c: c.age_ticks)

        # Check parents
        if not heir:
            living_parents = [
                all_agents[pid] for pid in deceased.parent_ids
                if pid in all_agents and all_agents[pid].alive
            ]
            if living_parents:
                heir = living_parents[0]

        # Check siblings
        if not heir and deceased.parent_ids:
            parent_set = set(deceased.parent_ids)
            living_siblings = [
                a for a in all_agents.values()
                if a.alive and a.agent_id != deceased_id and parent_set.intersection(a.parent_ids)
            ]
            if living_siblings:
                heir = max(living_siblings, key=lambda s: s.age_ticks)

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
                    if settlement_treasury_credit_fn and deceased.credits > 0:
                        settlement_treasury_credit_fn(parcel.settlement_id, deceased.credits)
                    results.append(
                        (parcel.parcel_id, "ESCHEATMENT_SETTLEMENT", parcel.settlement_id)
                    )
                else:
                    # Wilderness parcel reverts to UNCLAIMED
                    parcel.owner_id = None
                    parcel.owner_type = "UNCLAIMED"
                    parcel.for_sale_price = None
                    results.append((parcel.parcel_id, "ESCHEATMENT_WILDERNESS", "UNCLAIMED"))

        return results
