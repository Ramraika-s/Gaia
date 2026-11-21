"""
sim_core/society/borders.py
Five-tier territorial hierarchy, contiguous 16x16m parcel borders,
settlement status appeals, and Neutral Free City multi-racial validation.
Follows SOCIETY_AND_GOVERNANCE_SPEC.md Section 4.
"""

from __future__ import annotations

from typing import Any

from sim_core.schemas import SettlementTier

TIER_THRESHOLDS: dict[SettlementTier, dict[str, Any]] = {
    "VILLAGE": {"min_pop": 10, "min_parcels": 4, "min_treasury": 50.0},
    "TOWN": {"min_pop": 50, "min_parcels": 16, "min_treasury": 300.0},
    "CITY": {"min_pop": 250, "min_parcels": 48, "min_treasury": 1500.0},
    "STATE": {"min_pop": 600, "min_parcels": 100, "min_treasury": 5000.0},
    "NATION": {"min_pop": 1000, "min_parcels": 160, "min_treasury": 12000.0},
}


class BorderManager:
    """Manages explicit 16x16m parcel borders and settlement status appeals."""

    def __init__(self):
        # parcel_id -> settlement_id
        self.parcel_to_settlement: dict[str, str] = {}
        # settlement_id -> set of parcel_ids
        self.settlement_borders: dict[str, set[str]] = {}

    def register_settlement_border(self, settlement_id: str, parcel_ids: list[str]) -> bool:
        """Registers non-overlapping parcels to a settlement."""
        for pid in parcel_ids:
            if pid in self.parcel_to_settlement and self.parcel_to_settlement[pid] != settlement_id:
                return False  # Overlap detected

        self.settlement_borders.setdefault(settlement_id, set())
        for pid in parcel_ids:
            self.parcel_to_settlement[pid] = settlement_id
            self.settlement_borders[settlement_id].add(pid)
        return True

    def check_border_overlap(self, settlement_id: str, claimed_parcel_ids: list[str]) -> bool:
        """Returns True if any claimed parcel overlaps an existing different settlement."""
        for pid in claimed_parcel_ids:
            existing = self.parcel_to_settlement.get(pid)
            if existing and existing != settlement_id:
                return True
        return False

    def evaluate_settlement_appeal(
        self,
        settlement_id: str,
        appeal_kind: str,
        current_tier: SettlementTier,
        requested_tier: SettlementTier | None,
        living_pop: int,
        claimed_parcels: list[str],
        treasury_credits: float,
        demographics: dict[str, int] | None = None,
    ) -> tuple[bool, str]:
        """
        Adjudicates a SETTLEMENT_APPEAL:
        1. TIER_UPGRADE: validates pop, parcel count, treasury, and non-overlapping borders.
        2. NEUTRAL_FREE_CITY: requires tier == CITY and >= 2 races each with >= 15% share.
        """
        # 1. Neutral Free City Appeal
        if appeal_kind == "NEUTRAL_FREE_CITY":
            if current_tier != "CITY":
                return False, (
                    f"Rejected: Neutral Free City requires CITY tier, current is {current_tier}"
                )

            if not demographics or living_pop == 0:
                return False, "Rejected: missing population demographics"

            # Check >= 2 races at >= 15% share
            qualifying_races = [
                race for race, count in demographics.items()
                if (count / float(living_pop)) >= 0.15
            ]
            if len(qualifying_races) < 2:
                return False, "Rejected: Neutral Free City requires >=2 races at >=15% share"

            return True, "Neutral Free City approved: war_exempt granted"

        # 2. Tier Upgrade Appeal
        if appeal_kind == "TIER_UPGRADE":
            if not requested_tier or requested_tier not in TIER_THRESHOLDS:
                return False, f"Rejected: invalid requested tier '{requested_tier}'"

            thresholds = TIER_THRESHOLDS[requested_tier]

            # Check population
            if living_pop < thresholds["min_pop"]:
                return False, (
                    f"Rejected: population {living_pop} below threshold {thresholds['min_pop']}"
                )

            # Check parcel count
            if len(claimed_parcels) < thresholds["min_parcels"]:
                return False, (
                    f"Rejected: parcel count {len(claimed_parcels)} "
                    f"below threshold {thresholds['min_parcels']}"
                )

            # Check treasury
            if treasury_credits < thresholds["min_treasury"]:
                return False, (
                    f"Rejected: treasury {treasury_credits:.2f} "
                    f"below threshold {thresholds['min_treasury']:.2f}"
                )

            # Check border overlap
            if self.check_border_overlap(settlement_id, claimed_parcels):
                return False, "Rejected: border overlaps existing settlement"

            # Apply updated border
            self.register_settlement_border(settlement_id, claimed_parcels)
            return True, f"Tier upgrade to {requested_tier} approved"

        return False, f"Rejected: unknown appeal kind '{appeal_kind}'"
