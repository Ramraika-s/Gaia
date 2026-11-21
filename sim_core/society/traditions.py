"""
sim_core/society/traditions.py
Emergent cultural traditions, triggers, rituals, and taboo penalties.
Migrants carry memes across settlements and borders.
Follows SOCIETY_AND_GOVERNANCE_SPEC.md Section 6.2.
"""

from __future__ import annotations

import uuid
from typing import Literal

from sim_core.schemas import TraditionRecord

TraditionTrigger = Literal[
    "FIRST_DAY_OF_WINTER", "HARVEST_SURPLUS", "ROYAL_DEATH",
    "MARRIAGE", "WAR_VICTORY", "GOD_SIGHTING"
]

RitualAction = Literal[
    "GIFT_FOOD_IN_SQUARE", "GATHER_AT_TEMPLE", "SILENT_FAST",
    "PUBLIC_FEAST", "BUILD_MONUMENT_STEP"
]


class TraditionManager:
    """Manages cultural traditions, triggers, adoption, and taboo penalties."""

    def __init__(self):
        self.traditions: dict[str, TraditionRecord] = {}
        self.settlement_traditions: dict[str, set[str]] = {}

    def create_tradition(
        self,
        name: str,
        origin_settlement_id: str,
        trigger: TraditionTrigger,
        ritual_action: RitualAction,
        current_tick: int,
        adoption_rate: float = 0.15,
        taboo_penalty: float = 0.15,
    ) -> TraditionRecord:
        """Creates a new emergent tradition."""
        tradition_id = f"trad_{uuid.uuid4().hex[:12]}"
        tradition = TraditionRecord(
            tradition_id=tradition_id,
            name=name,
            origin_settlement_id=origin_settlement_id,
            trigger=trigger,
            ritual_action=ritual_action,
            adoption_rate=max(0.0, min(1.0, adoption_rate)),
            taboo_penalty=max(0.0, min(0.5, taboo_penalty)),
            created_tick=current_tick,
        )
        self.traditions[tradition_id] = tradition

        if origin_settlement_id not in self.settlement_traditions:
            self.settlement_traditions[origin_settlement_id] = set()
        self.settlement_traditions[origin_settlement_id].add(tradition_id)

        return tradition

    def spread_to_settlement(
        self,
        tradition_id: str,
        destination_settlement_id: str,
        spread_boost: float = 0.05,
    ) -> bool:
        """Migrant brings a tradition meme to a new settlement."""
        if tradition_id not in self.traditions:
            return False

        if destination_settlement_id not in self.settlement_traditions:
            self.settlement_traditions[destination_settlement_id] = set()

        self.settlement_traditions[destination_settlement_id].add(tradition_id)
        trad = self.traditions[tradition_id]
        trad.adoption_rate = min(1.0, trad.adoption_rate + spread_boost)
        return True

    def get_traditions_for_trigger(
        self,
        settlement_id: str,
        trigger: TraditionTrigger,
    ) -> list[TraditionRecord]:
        """Returns all traditions active in a settlement matching an event trigger."""
        trad_ids = self.settlement_traditions.get(settlement_id, set())
        matched = []
        for tid in trad_ids:
            trad = self.traditions.get(tid)
            if trad and trad.trigger == trigger:
                matched.append(trad)
        return matched

    def evaluate_compliance(
        self,
        tradition_id: str,
        did_ritual: bool,
    ) -> tuple[bool, float]:
        """
        Evaluates ritual compliance.
        If did_ritual is False, returns (False, taboo_penalty).
        If did_ritual is True, returns (True, 0.0).
        """
        trad = self.traditions.get(tradition_id)
        if not trad:
            return True, 0.0

        if not did_ritual:
            return False, trad.taboo_penalty

        # Successful ritual slightly reinforces adoption
        trad.adoption_rate = min(1.0, trad.adoption_rate + 0.01)
        return True, 0.0
