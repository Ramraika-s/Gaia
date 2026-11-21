"""
sim_core/society/religion.py
Faith dynamics, intent-scaled prayer gains, inactivity decay,
conregational altar prayers with Prayer Head aggregation, and Pope decree handling.
Follows DIVINE_HIERARCHY_SPEC.md Section 2 & SOCIETY_AND_GOVERNANCE_SPEC.md Section 2.
"""

from __future__ import annotations

import uuid
from typing import Any

from sim_core.config import TICKS_PER_GAME_DAY
from sim_core.schemas import AgentRecord as AgentState
from sim_core.schemas import DeitySlot, PrayerIntent

INTENT_PRAYER_GAINS: dict[PrayerIntent, tuple[float, float]] = {
    # intent -> (faith_devotion_delta, divine_energy_generated)
    "EARNEST": (0.045, 1.5),
    "CONGREGATIONAL": (0.035, 2.0),
    "CRISIS": (0.025, 1.0),
    "OBLIGATION": (0.012, 0.4),
    "PETITION": (0.020, 0.8),
    "GRATITUDE": (0.040, 1.2),
}


class ReligionManager:
    """Manages mortal faith devotion, prayers, and altar congregations."""

    def __init__(self):
        self.prayer_log: list[dict[str, Any]] = []

    @staticmethod
    def pray(
        agent: AgentState,
        target_deity_slot: DeitySlot,
        intent: PrayerIntent,
        current_tick: int,
        message: str = "",
    ) -> tuple[bool, str, float]:
        """
        Executes a mortal prayer.
        Hard Rule: Mortals can NEVER pray directly to God.
        Returns (success, reason, divine_energy_generated).
        """
        if target_deity_slot == "GOD" or target_deity_slot not in (
            "world_goddess", "gm_human", "gm_elf", "gm_dragon", "gm_beasthuman"
        ):
            return False, "FORBIDDEN: mortals cannot pray directly to God", 0.0

        faith_delta, energy_gen = INTENT_PRAYER_GAINS.get(intent, (0.02, 0.5))

        # Apply intent-scaled faith gain
        current_faith = agent.traits.get("faith_devotion", 0.0)
        agent.traits["faith_devotion"] = min(1.0, current_faith + faith_delta)
        agent.last_prayer_tick = current_tick

        return True, "PRAYER_DELIVERED", energy_gen

    @staticmethod
    def apply_inactivity_decay(agent: AgentState, current_tick: int) -> float:
        """
        If agent has not prayed in > 2 game days (2 * TICKS_PER_GAME_DAY),
        faith_devotion decays by -0.015 per game day.
        """
        if not agent.alive:
            return 0.0

        ticks_since_prayer = current_tick - agent.last_prayer_tick
        inactivity_threshold = 2 * TICKS_PER_GAME_DAY

        if ticks_since_prayer > inactivity_threshold:
            # -0.015 per game day, scaled per tick
            decay_per_tick = 0.015 / float(TICKS_PER_GAME_DAY)
            current_faith = agent.traits.get("faith_devotion", 0.0)
            new_faith = max(0.0, current_faith - decay_per_tick)
            agent.traits["faith_devotion"] = new_faith
            return current_faith - new_faith

        return 0.0

    @staticmethod
    def select_prayer_head(participants: list[AgentState]) -> AgentState:
        """
        Selects the congregational Prayer Head:
        1. Highest-devotion Oracle/Champion present
        2. Pope / Cleric present (cleric_rank != "NONE")
        3. Highest-devotion Elder
        4. Highest-devotion participant fallback
        """
        # 1. Oracle
        oracles = [a for a in participants if getattr(a, "is_oracle", False)]
        if oracles:
            return max(oracles, key=lambda o: o.traits.get("faith_devotion", 0.0))

        # 2. Cleric / Pope
        clerics = [a for a in participants if getattr(a, "cleric_rank", "NONE") != "NONE"]
        if clerics:
            return max(clerics, key=lambda c: c.traits.get("faith_devotion", 0.0))

        # 3. Elder
        elders = [a for a in participants if a.stage == "ELDER"]
        if elders:
            return max(elders, key=lambda e: e.traits.get("faith_devotion", 0.0))

        # 4. Fallback
        return max(participants, key=lambda p: p.traits.get("faith_devotion", 0.0))

    def assemble_congregational_prayer(
        self,
        participants: list[AgentState],
        target_deity_slot: DeitySlot,
        altar_name: str,
        current_tick: int,
        prayer_text: str = "We pray together for blessings over our people.",
    ) -> dict[str, Any]:
        """
        Aggregates >= 3 praying mortals into ONE unified congregational altar message
        led by the selected Prayer Head.
        """
        if len(participants) < 3:
            return {"error": "INSUFFICIENT_CONGREGATION: requires >= 3 participants"}

        prayer_head = self.select_prayer_head(participants)
        total_energy = 0.0

        for p in participants:
            _, _, energy = self.pray(
                p, target_deity_slot, "CONGREGATIONAL", current_tick, prayer_text
            )
            total_energy += energy

        head_rank = "CITIZEN"
        if getattr(prayer_head, "is_oracle", False):
            head_rank = "ORACLE"
        elif getattr(prayer_head, "cleric_rank", "NONE") == "POPE":
            head_rank = "POPE"
        elif getattr(prayer_head, "cleric_rank", "NONE") != "NONE":
            head_rank = "CLERIC"
        elif getattr(prayer_head, "stage", "") == "ELDER":
            head_rank = "ELDER"

        event = {
            "entry_id": f"congregation_{uuid.uuid4().hex[:8]}",
            "tick": current_tick,
            "altar_name": altar_name,
            "target_deity_slot": target_deity_slot,
            "group_size": len(participants),
            "mortal_count": len(participants),
            "prayer_head_id": prayer_head.agent_id,
            "prayer_head_name": prayer_head.display_name,
            "prayer_head_rank": head_rank,
            "message": f"[{altar_name} ({len(participants)} citizens) | "
                       f"Prayer Head: {prayer_head.display_name} -> {target_deity_slot}]: "
                       f'"{prayer_text}"',
            "total_divine_energy_generated": total_energy,
        }
        self.prayer_log.append(event)
        return event
