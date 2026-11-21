"""
sim_core/society/morality.py
Context-aware morality and relationship tracking.
Eliminates global "good vs. evil" scalars; tags harm events with immutable CombatContext
and maintains pairwise relationships and per-settlement civic standing.
Follows SOCIETY_AND_GOVERNANCE_SPEC.md Section 1.1.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, Field

from sim_core.schemas import CombatContext

RelationshipRole = Literal["STRANGER", "KIN", "ALLY", "RIVAL", "LEADER", "ORACLE"]


class Relationship(BaseModel):
    """Pairwise relationship between two mortal agents."""
    partner_id: str
    trust: float = Field(default=0.0, ge=-1.0, le=1.0)
    affinity: float = Field(default=0.0, ge=-1.0, le=1.0)
    fear: float = Field(default=0.0, ge=0.0, le=1.0)
    role: RelationshipRole = "STRANGER"


class AttackEvent(BaseModel):
    """Recent physical attack record stored in RAM for CombatContext attribution."""
    attacker_id: str
    victim_id: str
    tick: int
    x: float
    z: float


class MoralityEngine:
    """Classifies combat actions, tracks attacks, and manages per-settlement standing."""

    def __init__(self, recent_window_ticks: int = 60) -> None:
        self.recent_window_ticks = recent_window_ticks
        self.attack_history: list[AttackEvent] = []
        # agent_id -> {partner_id -> Relationship}
        self.relationships: dict[str, dict[str, Relationship]] = {}
        # settlement_id -> {agent_id -> standing}
        self.settlement_standing: dict[str, dict[str, float]] = {}

    def record_attack(
        self,
        attacker_id: str,
        victim_id: str,
        tick: int,
        x: float,
        z: float,
    ) -> None:
        """Records an attack event in RAM for context classification."""
        self.attack_history.append(
            AttackEvent(attacker_id=attacker_id, victim_id=victim_id, tick=tick, x=x, z=z)
        )
        # Prune older than recent_window_ticks
        cutoff = tick - self.recent_window_ticks
        self.attack_history = [e for e in self.attack_history if e.tick >= cutoff]

    def classify_combat_context(
        self,
        actor_id: str,
        target_id: str,
        current_tick: int,
        is_active_war: bool = False,
        kin_ids: set[str] | None = None,
        actor_pos: tuple[float, float] | None = None,
        is_sanctuary_trespass: bool = False,
    ) -> CombatContext:
        """
        Determines immutable CombatContext:
        1. ACTIVE_WAR: Nations/Cities in active war.
        2. SELF_DEFENSE: Target attacked or provoked actor within last 60 ticks.
        3. DEFENDING_KIN_OR_TOWN: Target attacked kin/townsperson within 60 ticks and 24m,
           or violently trespassed onto sanctuary.
        4. UNPROVOKED_ATTACK: None of the above.
        """
        if is_active_war:
            return "ACTIVE_WAR"

        cutoff = current_tick - self.recent_window_ticks
        kin_set = kin_ids or set()

        # Check SELF_DEFENSE: target attacked actor within window
        for event in reversed(self.attack_history):
            if event.tick < cutoff:
                break
            if event.attacker_id == target_id and event.victim_id == actor_id:
                return "SELF_DEFENSE"

        # Check DEFENDING_KIN_OR_TOWN
        if is_sanctuary_trespass:
            return "DEFENDING_KIN_OR_TOWN"

        for event in reversed(self.attack_history):
            if event.tick < cutoff:
                break
            if event.attacker_id == target_id and event.victim_id in kin_set:
                if actor_pos is not None:
                    dist = math.hypot(actor_pos[0] - event.x, actor_pos[1] - event.z)
                    if dist <= 24.0:
                        return "DEFENDING_KIN_OR_TOWN"
                else:
                    return "DEFENDING_KIN_OR_TOWN"

        return "UNPROVOKED_ATTACK"

    def get_relationship(self, agent_a: str, agent_b: str) -> Relationship:
        """Retrieves or initializes pairwise relationship from agent_a toward agent_b."""
        agent_rels = self.relationships.setdefault(agent_a, {})
        if agent_b not in agent_rels:
            agent_rels[agent_b] = Relationship(partner_id=agent_b)
        return agent_rels[agent_b]

    def update_standing(
        self,
        settlement_id: str,
        agent_id: str,
        delta: float,
    ) -> float:
        """Updates per-settlement civic standing in [-100.0, 100.0]."""
        s_dict = self.settlement_standing.setdefault(settlement_id, {})
        current = s_dict.get(agent_id, 0.0)
        new_val = max(-100.0, min(100.0, current + delta))
        s_dict[agent_id] = new_val
        return new_val

    def get_standing(self, settlement_id: str, agent_id: str) -> float:
        """Gets current civic standing in settlement."""
        return self.settlement_standing.get(settlement_id, {}).get(agent_id, 0.0)

    def evaluate_attack_inhibited(
        self,
        attacker_race: str,
        victim_race: str,
        attacker_traits: dict[str, float],
        is_self_defense: bool = False,
        is_survival: bool = False,
    ) -> bool:
        """
        Evaluates generational Dragon deterrence:
        Demons inherit a strong learned/generational caution weight against provoking
        Dragons (dragon_deterrence_bias) and refrain from unprovoked attacks on Dragons
        unless forced by survival or active self-defense.
        """
        if attacker_race == "DEMON" and victim_race == "DRAGON":
            if is_self_defense or is_survival:
                return False
            bias = attacker_traits.get("dragon_deterrence_bias", 0.65)
            return bias > 0.10
        return False

    def compute_racial_friction_modifier(
        self,
        actor_race: str,
        target_race: str,
        actor_traits: dict[str, float],
    ) -> float:
        """
        Computes emergent out-group friction:
        Demons carry a baseline out-group hostility/aggression prior toward non-Demons
        (subject to per-agent Gaussian variation so peaceful/diplomatic Demons can emerge).
        Toward Dragons, generational Dragon deterrence dampens outward aggression into caution.
        """
        if actor_race == target_race:
            return 0.0

        if actor_race == "DEMON" and target_race != "DEMON":
            aggression = actor_traits.get("out_group_aggression", 0.35)
            if target_race == "DRAGON":
                deterrence = actor_traits.get("dragon_deterrence_bias", 0.65)
                return max(0.0, aggression - deterrence * 0.8)
            return max(0.0, aggression)

        return 0.0
