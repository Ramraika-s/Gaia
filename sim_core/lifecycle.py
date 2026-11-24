"""
sim_core/lifecycle.py
Biology, developmental stage gates, infant distress & crying, gradual comforting,
opposite-gender mating, cross-species pregnancy & stillbirths, Age-10 mixed-race patronage,
Dragon metamorphosis, and permanent mortality.
Follows RACES_AND_BIOLOGY_SPEC.md, DIVINE_HIERARCHY_SPEC.md, and NEURAL_AND_LIFECYCLE_SPEC.md.
"""

from __future__ import annotations

import random
import uuid
from typing import Any

from sim_core.brains.personality import MoodState, generate_personality_vector
from sim_core.config import TICKS_PER_GAME_DAY
from sim_core.divine.hierarchy import RACE_TO_DEITY_SLOT
from sim_core.races import (
    CROSS_SPECIES_BIRTH_SURVIVAL_CHANCE,
    CROSS_SPECIES_CONCEPTION_CHANCE,
    BeasthumanSubLineage,
    get_race_profile,
)
from sim_core.schemas import (
    AgentRecord as AgentState,
)
from sim_core.schemas import (
    Gender,
    RaceId,
    RacialGodMotherSlot,
    Season,
    Vec3,
)
from sim_core.society.naming import generate_birth_name, inherit_dynasty_surname
from sim_core.society.seasons import SeasonManager

BASE_MAX_HP_BY_STAGE = {
    "INFANT": 40.0,
    "CHILD": 70.0,
    "ADULT": 100.0,
    "ELDER": 75.0,
}


class LifecycleManager:
    """Manages mortal biology, aging, health, distress, pregnancy, and dragon morphs."""

    @staticmethod
    def get_biological_age_years(agent: AgentState) -> float:
        """
        Maps calendar age to biological years:
        biological_age_years = (age_days / (6.0 * L)) * 18.0
        where ADULT = 18 biological years, and 10 years old = 3.333 * L game days.
        """
        profile = get_race_profile(agent.race, agent.sub_lineage)
        lifespan_l = max(0.1, profile.lifespan_multiplier)
        age_days = agent.age_ticks / float(TICKS_PER_GAME_DAY)
        return (age_days / (6.0 * lifespan_l)) * 18.0

    @staticmethod
    def get_max_health_for_stage(
        race: RaceId,
        stage: str,
        is_true_dragon: bool = False,
        sub_lineage: BeasthumanSubLineage | None = None,
    ) -> float:
        """Calculates stage-scaled max health multiplied by race profile."""
        profile = get_race_profile(race, sub_lineage)
        if is_true_dragon and race == "DRAGON":
            return profile.true_dragon_health
        base = BASE_MAX_HP_BY_STAGE.get(stage, 100.0)
        # Scaled proportionally to adult base health
        return base * (profile.base_max_health / 100.0)

    @classmethod
    def advance_agent_tick(
        cls,
        agent: AgentState,
        current_tick: int,
        season: Season = "SPRING",
        is_sheltered: bool = True,
        nearby_threat: bool = False,
        nearest_parent_dist: float = 20.0,
        true_dragon_aura_nearby: bool = False,
    ) -> None:
        """Performs one cognitive/biological tick update on an agent in RAM."""
        if not agent.alive:
            return

        profile = get_race_profile(agent.race, agent.sub_lineage)
        lifespan_l = max(0.1, profile.lifespan_multiplier)

        # 1. Aging & Stage Gate Transitions
        agent.age_ticks += 1
        age_days = agent.age_ticks / float(TICKS_PER_GAME_DAY)

        if agent.stage == "INFANT":
            # Promotion to CHILD: age >= 2*L and basic skills
            if (
                age_days >= 2.0 * lifespan_l
                and agent.skills.get("walk", 0.0) >= 0.35
                and agent.skills.get("self_care", 0.0) >= 0.35
            ):
                agent.stage = "CHILD"
                agent.max_health = cls.get_max_health_for_stage(
                    agent.race, "CHILD", sub_lineage=agent.sub_lineage
                )
                agent.health = min(agent.health + 30.0, agent.max_health)

        elif agent.stage == "CHILD":
            # Promotion to ADULT: age >= 6*L and competence
            walk = agent.skills.get("walk", 0.0)
            care = agent.skills.get("self_care", 0.0)
            forage = agent.skills.get("forage", 0.0)
            if age_days >= 6.0 * lifespan_l and ((walk + care + forage) / 3.0) >= 0.55:
                agent.stage = "ADULT"
                agent.max_health = cls.get_max_health_for_stage(
                    agent.race, "ADULT", sub_lineage=agent.sub_lineage
                )
                agent.health = agent.max_health
                if agent.race == "DRAGON" and agent.dragon_form is None:
                    agent.dragon_form = "HUMANOID_DRAGON"

        elif agent.stage == "ADULT":
            # Promotion to ELDER: age >= 24*L
            if age_days >= 24.0 * lifespan_l:
                agent.stage = "ELDER"
                agent.max_health = cls.get_max_health_for_stage(
                    agent.race, "ELDER", sub_lineage=agent.sub_lineage
                )
                agent.health = min(agent.health, agent.max_health)

        # 2. Cooldowns
        if agent.breeding_cooldown > 0:
            agent.breeding_cooldown -= 1

        # 3. Pregnancy Progress
        if agent.pregnant_ticks_remaining > 0:
            agent.pregnant_ticks_remaining -= 1

        # 4. Metabolic Hunger Decay
        hunger_mult = SeasonManager.get_hunger_multiplier(
            season=season,
            is_infant=(agent.stage == "INFANT"),
            is_sheltered=is_sheltered,
            winter_resistance=profile.winter_resistance,
        )
        if agent.pregnant_ticks_remaining > 0:
            hunger_mult *= 1.15  # Maternal metabolic cost

        hunger_drain = 0.005 * hunger_mult
        agent.hunger = max(0.0, agent.hunger - hunger_drain)

        # 5. Health Decay & Passive Regeneration
        if agent.hunger <= 0.0:
            # Starvation damage
            agent.health -= 0.02

        if agent.injured > 0.1 or agent.illness > 0.1:
            # Illness health drain; passive health regen disabled
            if agent.illness > 0.1:
                agent.health -= 0.01 * agent.illness
        else:
            # Healthy passive regen
            if agent.hunger > 60.0 and agent.health < agent.max_health:
                agent.health = min(agent.max_health, agent.health + 0.01)

        if agent.health <= 0.0:
            agent.alive = False
            agent.health = 0.0
            return

        # 6. Infant & Child Distress / Root-Cause Crying
        if agent.stage in ("INFANT", "CHILD"):
            distress_delta = 0.0
            if agent.hunger < 55.0:
                distress_delta += 0.05
            if agent.injured > 0.1 or agent.illness > 0.1:
                distress_delta += 0.05
            if season == "WINTER" and not is_sheltered:
                distress_delta += 0.06 / max(0.5, profile.winter_resistance)
            if nearby_threat or true_dragon_aura_nearby:
                distress_delta += 0.08
            if nearest_parent_dist > 12.0:
                distress_delta += 0.03

            agent.distress = max(0.0, min(1.0, agent.distress + distress_delta))
            # Crying triggers at distress >= 0.45
            agent.crying = agent.distress >= 0.45

        # 7. Dragon Metamorphosis Stamina & Auto-Reversion
        if agent.race == "DRAGON" and agent.dragon_form == "TRUE_DRAGON":
            # 1.8x continuous stamina drain
            agent.stamina = max(0.0, agent.stamina - (0.05 * 1.8))
            if agent.stamina < 15.0 or (not nearby_threat and agent.stamina < 30.0):
                # Auto-revert to HUMANOID_DRAGON
                cls.revert_dragon_metamorphosis(agent)

        # 8. Age-10 Mixed-Race Patronage Milestone Check
        if agent.secondary_heritage_race is not None and agent.patron_godmother_slot is None:
            bio_age = cls.get_biological_age_years(agent)
            if bio_age >= 10.0:
                cls.resolve_age10_patronage(agent)

    @staticmethod
    def soothe_or_comfort_child(
        parent: AgentState,
        child: AgentState,
        dist_meters: float,
    ) -> float:
        """
        Gradual comforting (COMFORT_OR_CARE_CHILD):
        Nearby caretaker (dist <= 4m) soothes distress by -0.06 to -0.10 per tick.
        No magic mute: root causes continue pushing distress up in advance_agent_tick.
        """
        if dist_meters > 4.0 or not child.alive:
            return 0.0

        teach_skill = parent.skills.get("teach", 0.0)
        care_skill = parent.skills.get("self_care", 0.0)
        reduction = 0.06 + 0.04 * min(1.0, (teach_skill + care_skill) / 2.0)

        old_distress = child.distress
        child.distress = max(0.0, child.distress - reduction)
        child.crying = child.distress >= 0.45
        return old_distress - child.distress

    @staticmethod
    def attempt_mating(
        p1: AgentState,
        p2: AgentState,
        current_tick: int,
        rng_seed: int | None = None,
    ) -> tuple[bool, str, dict[str, Any]]:
        """
        Evaluates mating proposal between two adults.
        Enforces binary opposite genders, Dragon humanoid form constraint,
        and 50% conception chance on cross-species pairings.
        """
        # Strict Binary Gender Rule
        if p1.gender == p2.gender:
            return False, "SAME_GENDER_MATING_FORBIDDEN: Mating requires BOY and GIRL", {}

        father = p1 if p1.gender == "BOY" else p2
        mother = p1 if p1.gender == "GIRL" else p2

        if father.stage != "ADULT" or mother.stage != "ADULT":
            return False, "STAGE_DISQUALIFIED: Mating requires ADULT agents", {}

        if not father.alive or not mother.alive:
            return False, "AGENT_NOT_ALIVE", {}

        if mother.pregnant_ticks_remaining > 0:
            return False, "ALREADY_PREGNANT: Mother is currently pregnant", {}

        if father.breeding_cooldown > 0 or mother.breeding_cooldown > 0:
            return False, "BREEDING_COOLDOWN_ACTIVE", {}

        if father.health < 0.7 * father.max_health or mother.health < 0.7 * mother.max_health:
            return False, "INSUFFICIENT_HEALTH: Requires >= 70% max health", {}

        if father.hunger < 60.0 or mother.hunger < 60.0:
            return False, "INSUFFICIENT_HUNGER: Requires >= 60 hunger", {}

        # Dragon Metamorphosis Constraint: Dragons must be in HUMANOID_DRAGON form
        for p in (father, mother):
            if p.race == "DRAGON" and p.dragon_form == "TRUE_DRAGON":
                return False, "TRUE_DRAGON_MATING_FORBIDDEN: Must be in HUMANOID_DRAGON form", {}

        rng = random.Random(rng_seed) if rng_seed is not None else random.Random()
        is_cross_species = father.race != mother.race

        # Conception Roll
        conception_chance = CROSS_SPECIES_CONCEPTION_CHANCE if is_cross_species else 1.00
        conceived = rng.random() < conception_chance

        mother_profile = get_race_profile(mother.race, mother.sub_lineage)
        base_cooldown = int(1.0 * mother_profile.breeding_cooldown_mult * TICKS_PER_GAME_DAY)

        if not conceived:
            # Failed conception: apply 0.25x short recovery cooldown
            short_cd = max(60, int(0.25 * base_cooldown))
            father.breeding_cooldown = short_cd
            mother.breeding_cooldown = short_cd
            return False, "CONCEPTION_FAILED", {"is_cross_species": is_cross_species}

        # Conception Success: Mother enters pregnancy
        gestation_ticks = int(mother_profile.gestation_days * TICKS_PER_GAME_DAY)
        mother.pregnant_ticks_remaining = gestation_ticks
        mother.pregnancy_father_id = father.agent_id
        mother.is_cross_species_pregnancy = is_cross_species
        mother.breeding_cooldown = gestation_ticks + base_cooldown
        father.breeding_cooldown = int(0.5 * base_cooldown)

        return (
            True,
            "CONCEPTION_SUCCESS",
            {
                "gestation_ticks": gestation_ticks,
                "gestation_days": mother_profile.gestation_days,
                "is_cross_species": is_cross_species,
                "mother_race": mother.race,
            },
        )

    @classmethod
    def deliver_child(
        cls,
        mother: AgentState,
        father: AgentState | None,
        current_tick: int,
        rng_seed: int | None = None,
        holy_nation_birth: bool = False,
    ) -> tuple[bool, AgentState | None, str]:
        """
        Executes delivery when pregnant_ticks_remaining reaches 0.
        Cross-species birth rolls 60% survival; stillbirth logs BIRTH_COMPLICATION
        with ZERO tensor slot allocated.
        """
        rng = random.Random(rng_seed) if rng_seed is not None else random.Random()
        is_cross = mother.is_cross_species_pregnancy

        # Survival Roll
        survival_chance = CROSS_SPECIES_BIRTH_SURVIVAL_CHANCE if is_cross else 1.00
        survived = rng.random() < survival_chance

        # Reset pregnancy state
        mother.pregnant_ticks_remaining = 0
        mother.pregnancy_father_id = None
        mother.is_cross_species_pregnancy = False

        if not survived:
            # Perinatal fatality: Stillbirth with zero tensor slot allocated
            return False, None, "BIRTH_COMPLICATION"

        # Survived: Generate newborn agent
        gender: Gender = "BOY" if rng.random() < 0.5 else "GIRL"

        if is_cross and father is not None:
            # 50/50 RNG dominant race
            dominant_race = mother.race if rng.random() < 0.5 else father.race
            secondary_race = father.race if dominant_race == mother.race else mother.race
            sub_lineage = mother.sub_lineage if dominant_race == mother.race else father.sub_lineage
            patron_slot = None  # Mixed-race child uncommitted under Age 10!
        else:
            dominant_race = mother.race
            secondary_race = None
            sub_lineage = mother.sub_lineage
            patron_slot = RACE_TO_DEITY_SLOT.get(dominant_race)

        # Phenotype Blending: HSV skin color
        p1_hsv = mother.skin_hsv
        p2_hsv = father.skin_hsv if father is not None else mother.skin_hsv
        blend_hsv = [
            round((p1_hsv[0] + p2_hsv[0]) / 2.0 + rng.gauss(0.0, 0.02), 3),
            round(max(0.0, min(1.0, (p1_hsv[1] + p2_hsv[1]) / 2.0 + rng.gauss(0.0, 0.04))), 3),
            round(max(0.0, min(1.0, (p1_hsv[2] + p2_hsv[2]) / 2.0 + rng.gauss(0.0, 0.04))), 3),
        ]

        # Naming
        birth_name = generate_birth_name(
            dominant_race, gender, sub_lineage, seed=rng.randint(0, 100000)
        )
        dynasty = inherit_dynasty_surname(
            mother.dynasty_surname,
            father.dynasty_surname if father is not None else None,
            dominant_race,
            sub_lineage,
            seed=rng.randint(0, 100000),
        )

        child_id = f"agent_{uuid.uuid4().hex[:8]}"
        parents = [mother.agent_id]
        if father is not None:
            parents.append(father.agent_id)

        # Traits & Faith Devotion Birth Imprinting
        base_faith = 0.0
        if dominant_race == "DEMON":
            # Demons receive elevated baseline devotion toward gm_demon
            base_faith = rng.uniform(0.35, 0.55)
        elif holy_nation_birth or (mother.traits.get("faith_devotion", 0.0) > 0.4):
            base_faith = rng.uniform(0.25, 0.45)

        # Initial godmother affinities
        godmother_affinities: dict[str, float] = {}
        if dominant_race == "DEMON":
            godmother_affinities["gm_demon"] = round(rng.uniform(0.35, 0.50), 3)

        traits: dict[str, float] = {
            "caution": round(rng.gauss(0.0, 0.08), 3),
            "sociability": round(rng.gauss(0.0, 0.08), 3),
            "ambition": round(rng.gauss(0.0, 0.08), 3),
            "loyalty": round(rng.gauss(0.0, 0.08), 3),
            "rule_respect": round(rng.gauss(0.0, 0.08), 3),
            "faith_devotion": round(max(-1.0, min(1.0, base_faith)), 3),
        }
        if dominant_race == "DEMON":
            traits["out_group_aggression"] = round(
                max(-1.0, min(1.0, 0.35 + rng.gauss(0.0, 0.08))), 3
            )
            traits["dragon_deterrence_bias"] = round(
                max(0.0, min(1.0, 0.65 + rng.gauss(0.0, 0.08))), 3
            )

        # Generate personality inheriting from parents and synchronize devotion
        parent_pvs = []
        if getattr(mother, "personality", None) is not None:
            parent_pvs.append(mother.personality)
        if father is not None and getattr(father, "personality", None) is not None:
            parent_pvs.append(father.personality)

        child_personality = generate_personality_vector(dominant_race, parents=parent_pvs, rng=rng)
        child_mood = MoodState(calm=0.8)
        if base_faith > 0.0:
            child_personality.devotion = round(max(0.0, min(1.0, base_faith)), 3)
            traits["faith_devotion"] = child_personality.devotion
        else:
            child_personality.devotion = round(child_personality.devotion, 3)
            traits["faith_devotion"] = child_personality.devotion

        newborn_max_health = cls.get_max_health_for_stage(
            dominant_race, "INFANT", sub_lineage=sub_lineage
        )

        child = AgentState(
            agent_id=child_id,
            slot_idx=0,
            display_name=f"{birth_name} {dynasty}",
            dynasty_surname=dynasty,
            gender=gender,
            race=dominant_race,
            sub_lineage=sub_lineage,
            secondary_heritage_race=secondary_race,
            dragon_form="HUMANOID_DRAGON" if dominant_race == "DRAGON" else None,
            patron_godmother_slot=patron_slot,
            godmother_affinities=godmother_affinities,
            skin_hsv=blend_hsv,
            stage="INFANT",
            age_ticks=0,
            health=newborn_max_health,
            max_health=newborn_max_health,
            hunger=100.0,
            stamina=100.0,
            parent_ids=parents,
            settlement_id=mother.settlement_id,
            nation_id=mother.nation_id,
            religion_id=mother.religion_id,
            pos=Vec3(x=mother.pos.x, y=mother.pos.y, z=mother.pos.z),
            traits=traits,
            personality=child_personality,
            mood=child_mood,
        )
        return True, child, "BIRTH_SUCCESS"

    @staticmethod
    def resolve_age10_patronage(
        child: AgentState,
        voluntary_choice: RacialGodMotherSlot | None = None,
        world_goddess_decision: RacialGodMotherSlot | None = None,
    ) -> str:
        """
        Resolves mixed-race patronage milestone at biological age 10:
        1. Voluntary choice locks target God-Mother.
        2. Timeout auto-allocates to deity with higher affinity.
        3. Exact tie escalates to World Goddess to decide and log decree.
        """
        if child.patron_godmother_slot is not None:
            return f"ALREADY_DEDICATED: {child.patron_godmother_slot}"

        gm_prim = RACE_TO_DEITY_SLOT.get(child.race)
        gm_sec = (
            RACE_TO_DEITY_SLOT.get(child.secondary_heritage_race)
            if child.secondary_heritage_race
            else None
        )

        valid_options: list[RacialGodMotherSlot] = [s for s in (gm_prim, gm_sec) if s is not None]
        if not valid_options:
            child.patron_godmother_slot = "gm_human"
            return "DEFAULTED_HUMAN"

        # 1. Voluntary Choice
        if voluntary_choice in valid_options:
            child.patron_godmother_slot = voluntary_choice
            return f"VOLUNTARY_CHOICE_LOCKED: {voluntary_choice}"

        # 2. Affinity comparison
        aff_prim = child.godmother_affinities.get(gm_prim, 0.0) if gm_prim else 0.0
        aff_sec = child.godmother_affinities.get(gm_sec, 0.0) if gm_sec else 0.0

        if abs(aff_prim - aff_sec) > 1e-4:
            winner = gm_prim if aff_prim > aff_sec else gm_sec
            child.patron_godmother_slot = winner
            return f"AUTO_ALLOCATED_HIGHER_AFFINITY: {winner} ({max(aff_prim, aff_sec):.3f})"

        # 3. Exact Tie -> Escalates to World Goddess
        if world_goddess_decision in valid_options:
            child.patron_godmother_slot = world_goddess_decision
            return f"WORLD_GODDESS_TIE_BREAK_DECREE: {world_goddess_decision}"

        # Default tie fallback
        fallback: RacialGodMotherSlot = gm_prim if gm_prim is not None else valid_options[0]
        child.patron_godmother_slot = fallback
        return f"WORLD_GODDESS_TIE_BREAK_DEFAULT: {fallback}"

    @classmethod
    def trigger_dragon_metamorphosis(cls, dragon: AgentState) -> bool:
        """Shifts an Adult/Elder Dragon from HUMANOID_DRAGON to TRUE_DRAGON form."""
        if dragon.race != "DRAGON" or dragon.stage not in ("ADULT", "ELDER"):
            return False
        if dragon.dragon_form == "TRUE_DRAGON":
            return False

        dragon.dragon_form = "TRUE_DRAGON"
        dragon.max_health = 650.0
        dragon.health = min(650.0, dragon.health * (650.0 / 280.0))
        return True

    @classmethod
    def revert_dragon_metamorphosis(cls, dragon: AgentState) -> bool:
        """Reverts an Adult/Elder Dragon back to HUMANOID_DRAGON form."""
        if dragon.race != "DRAGON" or dragon.dragon_form != "TRUE_DRAGON":
            return False

        dragon.dragon_form = "HUMANOID_DRAGON"
        dragon.max_health = 280.0
        dragon.health = min(280.0, dragon.health * (280.0 / 650.0))
        return True
