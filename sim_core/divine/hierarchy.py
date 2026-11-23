"""
sim_core/divine/hierarchy.py
The Three-Tier Divine Family Hierarchy:
God -> World Goddess -> 4 Racial God-Mothers.
Enforces bestowed naming, finite divine energy, intervention cooldowns,
mortal oracles (max 3/race), and the Non-Aggression Covenant.
Follows DIVINE_HIERARCHY_SPEC.md Sections 1, 3, and 4.
"""

from __future__ import annotations

from sim_core.brains.personality import MoodState, PersonalityVector
from sim_core.schemas import (
    DeitySlot,
    DivineEntityRecord,
    DivinePersonality,
    RaceId,
    RacialGodMotherSlot,
)

INTERVENTION_SPECS: dict[str, dict[str, float | int]] = {
    "SOOTHE_OR_HEAL": {"cost": 25.0, "cooldown_ticks": 120},
    "INSPIRE_SCHOLAR_OR_CRAFT": {"cost": 40.0, "cooldown_ticks": 300},
    "HARVEST_OR_WARMTH_BLESSING": {"cost": 140.0, "cooldown_ticks": 10800},
    "WARD_DEFENDERS": {"cost": 180.0, "cooldown_ticks": 16200},
    "BLESS_ORACLE": {"cost": 200.0, "cooldown_ticks": 75600},
}

RACE_TO_DEITY_SLOT: dict[RaceId, RacialGodMotherSlot] = {
    "HUMAN": "gm_human",
    "ELF": "gm_elf",
    "DRAGON": "gm_dragon",
    "BEASTHUMAN": "gm_beasthuman",
    "DEMON": "gm_demon",
}


class DivineHierarchyManager:
    """Manages the World Goddess and 4 Racial God-Mothers in RAM."""

    def __init__(self) -> None:
        self.entities: dict[DeitySlot, DivineEntityRecord] = {
            "world_goddess": DivineEntityRecord(
                slot="world_goddess",
                bestowed_name="Gaia",
                role="WORLD_GODDESS",
                patron_race=None,
                divine_energy=1000.0,
                personality=DivinePersonality(
                    compassion=0.8, restraint=0.8, pride=0.2, protective_fury=0.4, diplomacy=0.9
                ),
                personality_vector=PersonalityVector(
                    courage=0.7,
                    empathy=0.85,
                    ambition=0.6,
                    discipline=0.85,
                    curiosity=0.8,
                    devotion=0.9,
                    honesty=0.9,
                    out_group_trust=0.75,
                    caution=0.7,
                    pride=0.4,
                ),
                mood=MoodState(calm=0.85, inspired=0.6),
            ),
            "gm_human": DivineEntityRecord(
                slot="gm_human",
                bestowed_name="Solis",
                role="RACIAL_GOD_MOTHER",
                patron_race="HUMAN",
                divine_energy=300.0,
                personality=DivinePersonality(
                    compassion=0.65,
                    restraint=0.60,
                    diplomacy=0.70,
                    protective_fury=0.50,
                    pride=0.55,
                ),
                personality_vector=PersonalityVector(
                    courage=0.65,
                    empathy=0.7,
                    ambition=0.7,
                    discipline=0.65,
                    curiosity=0.7,
                    devotion=0.8,
                    honesty=0.7,
                    out_group_trust=0.65,
                    caution=0.55,
                    pride=0.55,
                ),
                mood=MoodState(calm=0.7, inspired=0.5),
            ),
            "gm_elf": DivineEntityRecord(
                slot="gm_elf",
                bestowed_name="Aria",
                role="RACIAL_GOD_MOTHER",
                patron_race="ELF",
                divine_energy=300.0,
                personality=DivinePersonality(
                    restraint=0.75,
                    compassion=0.60,
                    pride=0.70,
                    diplomacy=0.65,
                    protective_fury=0.55,
                ),
                personality_vector=PersonalityVector(
                    courage=0.55,
                    empathy=0.65,
                    ambition=0.5,
                    discipline=0.85,
                    curiosity=0.85,
                    devotion=0.8,
                    honesty=0.8,
                    out_group_trust=0.55,
                    caution=0.75,
                    pride=0.7,
                ),
                mood=MoodState(calm=0.8, inspired=0.6),
            ),
            "gm_dragon": DivineEntityRecord(
                slot="gm_dragon",
                bestowed_name="Pyra",
                role="RACIAL_GOD_MOTHER",
                patron_race="DRAGON",
                divine_energy=300.0,
                personality=DivinePersonality(
                    restraint=0.85,
                    pride=0.80,
                    protective_fury=0.85,
                    compassion=0.45,
                    diplomacy=0.50,
                ),
                personality_vector=PersonalityVector(
                    courage=0.9,
                    empathy=0.45,
                    ambition=0.8,
                    discipline=0.75,
                    curiosity=0.6,
                    devotion=0.75,
                    honesty=0.85,
                    out_group_trust=0.4,
                    caution=0.7,
                    pride=0.85,
                ),
                mood=MoodState(calm=0.75, inspired=0.4),
            ),
            "gm_beasthuman": DivineEntityRecord(
                slot="gm_beasthuman",
                bestowed_name="Terra",
                role="RACIAL_GOD_MOTHER",
                patron_race="BEASTHUMAN",
                divine_energy=300.0,
                personality=DivinePersonality(
                    protective_fury=0.75,
                    compassion=0.65,
                    restraint=0.45,
                    pride=0.70,
                    diplomacy=0.55,
                ),
                personality_vector=PersonalityVector(
                    courage=0.8,
                    empathy=0.7,
                    ambition=0.6,
                    discipline=0.6,
                    curiosity=0.65,
                    devotion=0.8,
                    honesty=0.75,
                    out_group_trust=0.5,
                    caution=0.5,
                    pride=0.65,
                ),
                mood=MoodState(calm=0.65, inspired=0.5),
            ),
            "gm_demon": DivineEntityRecord(
                slot="gm_demon",
                bestowed_name="Morvath",
                role="RACIAL_GOD_MOTHER",
                patron_race="DEMON",
                divine_energy=300.0,
                personality=DivinePersonality(
                    protective_fury=0.80,
                    pride=0.75,
                    restraint=0.50,
                    compassion=0.40,
                    diplomacy=0.50,
                ),
                personality_vector=PersonalityVector(
                    courage=0.85,
                    empathy=0.4,
                    ambition=0.85,
                    discipline=0.7,
                    curiosity=0.75,
                    devotion=0.9,
                    honesty=0.6,
                    out_group_trust=0.35,
                    caution=0.75,
                    pride=0.8,
                ),
                mood=MoodState(calm=0.6, inspired=0.5),
            ),
        }

    def bestow_name(self, slot: DeitySlot, new_name: str) -> str:
        """God bestows a custom name onto the Goddess or a God-Mother."""
        entity = self.entities[slot]
        entity.bestowed_name = new_name.strip()
        return entity.bestowed_name

    def get_deity(self, slot: DeitySlot) -> DivineEntityRecord:
        return self.entities[slot]

    def add_divine_energy(self, slot: DeitySlot, delta: float) -> float:
        """Adds or deducts Divine Energy, bounded in [0.0, 1000.0]."""
        entity = self.entities[slot]
        current = entity.divine_energy
        new_val = max(0.0, min(1000.0, current + delta))
        # Passive decay if above 800.0
        if new_val > 800.0 and delta > 0:
            new_val -= 0.1 * (new_val - 800.0)
        entity.divine_energy = round(new_val, 2)
        return entity.divine_energy

    def can_intervene(
        self,
        slot: DeitySlot,
        action: str,
        current_tick: int,
        target_civilians: bool = False,
        target_slot: DeitySlot | None = None,
    ) -> tuple[bool, str]:
        """
        Validates intervention eligibility under the Non-Aggression Covenant,
        Divine Truces, cooldowns, and Divine Energy costs.
        """
        entity = self.entities[slot]

        # 1. Non-Aggression Covenant Guard
        if target_civilians and entity.role == "RACIAL_GOD_MOTHER":
            entity.covenant_rebukes += 1
            return False, "NON_AGGRESSION_COVENANT_BREACH: Smites against rival civilians forbidden"

        # 2. Cooldown Guard
        if current_tick < entity.intervention_cooldown_until_tick:
            remaining = entity.intervention_cooldown_until_tick - current_tick
            return False, f"COOLDOWN_ACTIVE: {remaining} ticks remaining"

        # 3. Active Truce Guard
        if action == "WARD_DEFENDERS" and target_slot is not None:
            if target_slot in entity.active_truce_with:
                return (
                    False,
                    f"DIVINE_TRUCE_ACTIVE: Mutual truce with '{target_slot}' blocks war wards",
                )

        # 4. Energy Cost Guard
        spec = INTERVENTION_SPECS.get(action)
        if spec is None:
            return False, f"UNKNOWN_INTERVENTION: '{action}'"

        cost = float(spec["cost"])
        if entity.divine_energy < cost:
            return False, f"INSUFFICIENT_ENERGY: Requires {cost}, has {entity.divine_energy}"

        return True, "SUCCESS"

    def execute_intervention(
        self,
        slot: DeitySlot,
        action: str,
        current_tick: int,
        target_civilians: bool = False,
        target_slot: DeitySlot | None = None,
    ) -> tuple[bool, str]:
        """Executes intervention, consumes Divine Energy, and applies cooldown."""
        allowed, reason = self.can_intervene(
            slot, action, current_tick, target_civilians, target_slot
        )
        if not allowed:
            return False, reason

        entity = self.entities[slot]
        spec = INTERVENTION_SPECS[action]
        entity.divine_energy = round(entity.divine_energy - float(spec["cost"]), 2)
        entity.intervention_cooldown_until_tick = current_tick + int(spec["cooldown_ticks"])
        return True, f"EXECUTED: {action} by {entity.bestowed_name}"

    def appoint_oracle(
        self,
        slot: DeitySlot,
        agent_id: str,
        faith_devotion: float,
        has_criminal_record: bool = False,
    ) -> tuple[bool, str]:
        """Appoints a mortal Oracle / Champion (max 3 living active per race)."""
        entity = self.entities[slot]
        if len(entity.oracle_agent_ids) >= 3:
            return False, "MAX_ORACLES_REACHED: Race already has 3 active Oracles"
        if faith_devotion < 0.65:
            return False, f"INSUFFICIENT_FAITH: Requires >= 0.65, has {faith_devotion:.2f}"
        if has_criminal_record:
            return False, "CRIMINAL_RECORD_DISQUALIFIED: Candidate has domestic criminal record"

        if agent_id not in entity.oracle_agent_ids:
            entity.oracle_agent_ids.append(agent_id)
        return True, f"ORACLE_APPOINTED: {agent_id} for {entity.bestowed_name}"

    def remove_oracle(self, slot: DeitySlot, agent_id: str) -> bool:
        """Removes an oracle on death."""
        entity = self.entities[slot]
        if agent_id in entity.oracle_agent_ids:
            entity.oracle_agent_ids.remove(agent_id)
            return True
        return False

    def is_oracle(self, agent_id: str) -> bool:
        """Checks if agent_id is an active Oracle for any race."""
        for e in self.entities.values():
            if agent_id in e.oracle_agent_ids:
                return True
        return False
