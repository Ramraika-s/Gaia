"""
sim_core/society/politics.py
Five-tier polities (VILLAGE -> TOWN -> CITY -> STATE -> NATION),
regime successions, elections, wars, and Elder appointments.
Follows SOCIETY_AND_GOVERNANCE_SPEC.md Section 4 & 6.
"""

from __future__ import annotations

from sim_core.schemas import AgentRecord as AgentState
from sim_core.schemas import SettlementTier


class Polity:
    """Represents a settlement or sovereign nation."""

    def __init__(
        self,
        settlement_id: str,
        name: str,
        tier: SettlementTier = "VILLAGE",
        regime_type: str = "CHIEFDOM",
        leader_id: str | None = None,
        treasury_credits: float = 100.0,
        tax_rate: float = 0.05,
        tariff_rate: float = 0.0,
        is_neutral_free_city: bool = False,
        war_exempt: bool = False,
    ):
        self.settlement_id = settlement_id
        self.name = name
        self.tier = tier
        self.regime_type = regime_type
        self.leader_id = leader_id
        self.treasury_credits = treasury_credits
        self.tax_rate = max(0.0, min(0.30, tax_rate))
        self.tariff_rate = max(0.0, min(0.50, tariff_rate))
        self.is_neutral_free_city = is_neutral_free_city
        self.war_exempt = war_exempt or is_neutral_free_city

        self.border_parcels: set[str] = set()
        self.at_war_with: set[str] = set()
        self.allied_with: set[str] = set()
        self.appointed_library_elders: list[str] = []

    def appoint_library_elder(self, elder_agent_id: str) -> tuple[bool, str]:
        """Appoints an Elder to the World Library Council (max 2 per NATION)."""
        if self.tier != "NATION":
            return False, (
                f"Rejected: only NATION tier may appoint Library Elders, current is {self.tier}"
            )

        if len(self.appointed_library_elders) >= 2:
            return False, "Rejected: nation already has maximum 2 Library Elders"

        if elder_agent_id in self.appointed_library_elders:
            return False, "Rejected: elder already appointed"

        self.appointed_library_elders.append(elder_agent_id)
        return True, "Elder appointed to World Library Council"


class PoliticalEngine:
    """Manages political successions, elections, wars, and Elder appointments."""

    def __init__(self):
        self.polities: dict[str, Polity] = {}

    def register_polity(self, polity: Polity) -> None:
        self.polities[polity.settlement_id] = polity

    def declare_war(self, initiator_id: str, target_id: str) -> tuple[bool, str]:
        """
        Declares war between two polities.
        Neutral Free Cities (war_exempt = True) are barred from declaring offensive war.
        """
        if initiator_id not in self.polities or target_id not in self.polities:
            return False, "UNKNOWN_POLITY"

        initiator = self.polities[initiator_id]
        target = self.polities[target_id]

        if initiator.war_exempt or initiator.is_neutral_free_city:
            return False, "Rejected: Neutral Free Cities cannot declare offensive war"

        if target_id in initiator.at_war_with:
            return False, "ALREADY_AT_WAR"

        initiator.at_war_with.add(target_id)
        target.at_war_with.add(initiator_id)
        return True, f"War declared between {initiator.name} and {target.name}"

    def sign_peace(self, polity_a_id: str, polity_b_id: str) -> tuple[bool, str]:
        """Signs peace treaty concluding an active war."""
        if polity_a_id not in self.polities or polity_b_id not in self.polities:
            return False, "UNKNOWN_POLITY"

        p_a = self.polities[polity_a_id]
        p_b = self.polities[polity_b_id]

        p_a.at_war_with.discard(polity_b_id)
        p_b.at_war_with.discard(polity_a_id)
        return True, "Peace treaty concluded"

    def execute_monarchy_succession(
        self,
        polity: Polity,
        deceased_king: AgentState,
        all_agents: dict[str, AgentState],
    ) -> tuple[bool, str, str | None]:
        """
        Monarchy succession cascade:
        1. Eldest living adult child
        2. Any living child
        3. Living sibling
        4. Succession crisis fallback
        """
        deceased_id = deceased_king.agent_id
        living_children = [
            a for a in all_agents.values()
            if a.alive and deceased_id in a.parent_ids
        ]

        if living_children:
            adult_children = [c for c in living_children if c.stage in ("ADULT", "ELDER")]
            if adult_children:
                heir = max(adult_children, key=lambda c: c.age_ticks)
            else:
                heir = max(living_children, key=lambda c: c.age_ticks)
            polity.leader_id = heir.agent_id
            return True, "ROYAL_SUCCESSION_HEIR", heir.agent_id

        # Sibling fallback
        if deceased_king.parent_ids:
            parent_set = set(deceased_king.parent_ids)
            living_siblings = [
                a for a in all_agents.values()
                if a.alive and a.agent_id != deceased_id and parent_set.intersection(a.parent_ids)
            ]
            if living_siblings:
                heir = max(living_siblings, key=lambda s: s.age_ticks)
                polity.leader_id = heir.agent_id
                return True, "ROYAL_SUCCESSION_SIBLING", heir.agent_id

        # Succession crisis: pick highest-ambition elder or citizen
        citizens = [
            a for a in all_agents.values()
            if a.alive and a.settlement_id == polity.settlement_id and a.stage in ("ADULT", "ELDER")
        ]
        if citizens:
            new_leader = max(citizens, key=lambda c: c.traits.get("ambition", 0.0))
            polity.leader_id = new_leader.agent_id
            return True, "SUCCESSION_CRISIS_COUNCIL_LEADER", new_leader.agent_id

        return False, "SUCCESSION_CRISIS_NO_CITIZENS", None
