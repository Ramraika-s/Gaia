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
from sim_core.schemas import DeitySlot, PrayerIntent, ReligionRecord

INTENT_PRAYER_GAINS: dict[PrayerIntent, tuple[float, float]] = {
    # intent -> (faith_devotion_delta, divine_energy_generated)
    "EARNEST_VOLUNTARY": (0.045, 1.5),
    "GRATITUDE": (0.040, 1.2),
    "CONGREGATIONAL_ALTAR": (0.035, 2.0),
    "CRISIS_PLEA": (0.025, 1.0),
    "PARENT_DIRECTED": (0.012, 0.4),
    "OBLIGATION": (0.012, 0.4),
    "PETITION": (0.020, 0.8),
}


def get_agent_devotion(agent: AgentState) -> float:
    """
    Single source of truth reading synchronized devotion in [0.0, 1.0].
    Reads agent.personality.devotion if personality exists, else agent.traits['faith_devotion'].
    """
    pers = getattr(agent, "personality", None)
    if pers is not None and hasattr(pers, "devotion"):
        return max(0.0, min(1.0, float(pers.devotion)))
    return max(0.0, min(1.0, float(agent.traits.get("faith_devotion", 0.0))))


def set_agent_devotion(agent: AgentState, value: float) -> float:
    """
    Clamps value to [0.0, 1.0] and synchronizes both agent.traits['faith_devotion']
    and agent.personality.devotion (if agent.personality is not None).
    Returns the clamped devotion value.
    """
    clamped = max(0.0, min(1.0, float(value)))
    agent.traits["faith_devotion"] = clamped
    pers = getattr(agent, "personality", None)
    if pers is not None and hasattr(pers, "devotion"):
        pers.devotion = clamped
    return clamped


class ReligionManager:
    """Manages mortal faith devotion, prayers, organized religions, and altar congregations."""

    def __init__(self) -> None:
        self.prayer_log: list[dict[str, Any]] = []
        self.religions: dict[str, ReligionRecord] = {}
        self.seed_default_faiths()

    def register_religion(self, record: ReligionRecord) -> None:
        """Registers an organized religion."""
        self.religions[record.religion_id] = record

    def seed_default_faiths(self) -> None:
        """Seeds default canonical faiths for World Goddess and the 5 God-Mothers."""
        defaults = [
            ReligionRecord(
                religion_id="rel_world_goddess",
                name="Order of the World Goddess",
                aligned_deity_slot="world_goddess",
                founder_id="system_divine",
                tenets={
                    "pacifism": 0.7,
                    "charity_tithe_rate": 0.05,
                    "work_ethic": 0.6,
                    "sacred_land_defense": 0.8,
                    "heresy_intolerance": 0.1,
                },
                canonized_entry_ids=["canon_world_harmony_01"],
            ),
            ReligionRecord(
                religion_id="rel_gm_human",
                name="Church of the First Mother",
                aligned_deity_slot="gm_human",
                founder_id="system_divine",
                tenets={
                    "pacifism": 0.4,
                    "charity_tithe_rate": 0.05,
                    "work_ethic": 0.8,
                    "sacred_land_defense": 0.6,
                    "heresy_intolerance": 0.2,
                },
                canonized_entry_ids=["canon_human_covenant_01"],
            ),
            ReligionRecord(
                religion_id="rel_gm_elf",
                name="Covenant of the Sylph Queen",
                aligned_deity_slot="gm_elf",
                founder_id="system_divine",
                tenets={
                    "pacifism": 0.8,
                    "charity_tithe_rate": 0.04,
                    "work_ethic": 0.5,
                    "sacred_land_defense": 0.7,
                    "heresy_intolerance": 0.15,
                },
                canonized_entry_ids=["canon_sylph_covenant_01"],
            ),
            ReligionRecord(
                religion_id="rel_gm_dragon",
                name="Cult of the Primordial Flame",
                aligned_deity_slot="gm_dragon",
                founder_id="system_divine",
                tenets={
                    "pacifism": 0.3,
                    "charity_tithe_rate": 0.06,
                    "work_ethic": 0.7,
                    "sacred_land_defense": 0.95,
                    "heresy_intolerance": 0.3,
                },
                canonized_entry_ids=["canon_dragon_flame_01"],
            ),
            ReligionRecord(
                religion_id="rel_gm_beasthuman",
                name="Fang and Claw Brotherhood",
                aligned_deity_slot="gm_beasthuman",
                founder_id="system_divine",
                tenets={
                    "pacifism": 0.4,
                    "charity_tithe_rate": 0.05,
                    "work_ethic": 0.75,
                    "sacred_land_defense": 0.7,
                    "heresy_intolerance": 0.2,
                },
                canonized_entry_ids=["canon_beasthuman_brotherhood_01"],
            ),
            ReligionRecord(
                religion_id="rel_gm_demon",
                name="Abyssal Creed",
                aligned_deity_slot="gm_demon",
                founder_id="system_divine",
                tenets={
                    "pacifism": 0.2,
                    "charity_tithe_rate": 0.08,
                    "work_ethic": 0.85,
                    "sacred_land_defense": 0.9,
                    "heresy_intolerance": 0.4,
                },
                canonized_entry_ids=["canon_abyssal_creed_01"],
            ),
        ]
        for r in defaults:
            self.register_religion(r)

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
            "world_goddess",
            "gm_human",
            "gm_elf",
            "gm_dragon",
            "gm_beasthuman",
            "gm_demon",
        ):
            return False, "FORBIDDEN: mortals cannot pray directly to God", 0.0

        faith_delta, energy_gen = INTENT_PRAYER_GAINS.get(intent, (0.02, 0.5))

        # Apply intent-scaled faith gain through canonical setter
        current_faith = get_agent_devotion(agent)
        set_agent_devotion(agent, current_faith + faith_delta)
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
            current_faith = get_agent_devotion(agent)
            new_faith = set_agent_devotion(agent, current_faith - decay_per_tick)
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
            return max(oracles, key=lambda o: get_agent_devotion(o))

        # 2. Cleric / Pope
        clerics = [a for a in participants if getattr(a, "cleric_rank", "NONE") != "NONE"]
        if clerics:
            return max(clerics, key=lambda c: get_agent_devotion(c))

        # 3. Elder
        elders = [a for a in participants if a.stage == "ELDER"]
        if elders:
            return max(elders, key=lambda e: get_agent_devotion(e))

        # 4. Fallback
        return max(participants, key=lambda p: get_agent_devotion(p))

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
                p, target_deity_slot, "CONGREGATIONAL_ALTAR", current_tick, prayer_text
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
