"""
sim_core/races.py
Biological specifications, Master Multiplier Table, and RaceProfile registry
for the 5 distinct races (HUMAN, ELF, DRAGON, BEASTHUMAN, DEMON) and 2 biological genders.
"""

from __future__ import annotations

from typing import Literal, cast

from pydantic import BaseModel, Field

Gender = Literal["BOY", "GIRL"]
RaceId = Literal["HUMAN", "ELF", "DRAGON", "BEASTHUMAN", "DEMON"]
BeasthumanSubLineage = Literal["CAT_KIN", "DWARF", "WOLF_KIN", "BARBARIAN", "BEAR_KIN"]
DragonForm = Literal["HUMANOID_DRAGON", "TRUE_DRAGON"]

# Probabilities for cross-species reproduction
CROSS_SPECIES_CONCEPTION_CHANCE: float = 0.50
CROSS_SPECIES_BIRTH_SURVIVAL_CHANCE: float = 0.60


class RaceProfile(BaseModel):
    race_id: RaceId
    sub_lineage: BeasthumanSubLineage | None = None
    patron_godmother_slot: str  # "gm_human", "gm_elf", "gm_dragon", "gm_beasthuman", "gm_demon"
    base_max_health: float = 100.0
    lifespan_multiplier: float = 1.0
    gestation_days: float = 1.5  # Mother's race gestation duration in Game Days
    breeding_cooldown_mult: float = 1.0
    neuroplasticity_mult: float = 1.0
    winter_resistance: float = 1.0
    movement_speed_mult: float = 1.0
    adult_scale_height: float = 1.0
    adult_scale_width: float = 1.0
    can_metamorphose: bool = False
    true_dragon_health: float = 650.0
    true_dragon_scale: float = 3.8
    skill_affinities: dict[str, float] = Field(default_factory=dict)
    trait_priors: dict[str, float] = Field(default_factory=dict)
    compatible_breeding_races: list[RaceId] = Field(
        default_factory=lambda: ["HUMAN", "ELF", "DRAGON", "BEASTHUMAN", "DEMON"]
    )


# Master Multiplier Table from RACES_AND_BIOLOGY_SPEC.md
RACE_REGISTRY: dict[tuple[RaceId, BeasthumanSubLineage | None] | str, RaceProfile] = {
    ("HUMAN", None): RaceProfile(
        race_id="HUMAN",
        sub_lineage=None,
        patron_godmother_slot="gm_human",
        base_max_health=100.0,
        lifespan_multiplier=1.0,
        gestation_days=1.5,
        breeding_cooldown_mult=1.0,
        neuroplasticity_mult=1.15,
        winter_resistance=1.0,
        movement_speed_mult=1.0,
        adult_scale_height=1.00,
        adult_scale_width=1.00,
        trait_priors={"ambition": 0.25, "sociability": 0.15, "rule_respect": 0.05},
        skill_affinities={"trade": 0.15, "build": 0.10},
    ),
    ("ELF", None): RaceProfile(
        race_id="ELF",
        sub_lineage=None,
        patron_godmother_slot="gm_elf",
        base_max_health=95.0,
        lifespan_multiplier=3.0,
        gestation_days=4.0,
        breeding_cooldown_mult=2.5,
        neuroplasticity_mult=1.00,
        winter_resistance=1.15,
        movement_speed_mult=1.0,
        adult_scale_height=1.06,
        adult_scale_width=1.00,
        trait_priors={"caution": 0.20, "loyalty": 0.30, "rule_respect": 0.20, "ambition": -0.10},
        skill_affinities={"forage": 0.25, "self_care": 0.20, "teach": 0.25},
    ),
    ("DRAGON", None): RaceProfile(
        race_id="DRAGON",
        sub_lineage=None,
        patron_godmother_slot="gm_dragon",
        base_max_health=280.0,
        lifespan_multiplier=6.0,
        gestation_days=7.0,
        breeding_cooldown_mult=5.0,
        neuroplasticity_mult=0.85,
        winter_resistance=1.80,
        movement_speed_mult=1.0,
        adult_scale_height=1.05,
        adult_scale_width=1.00,
        can_metamorphose=True,
        true_dragon_health=650.0,
        true_dragon_scale=3.8,
        trait_priors={"caution": 0.15, "loyalty": 0.35, "ambition": -0.25, "sociability": -0.25},
        skill_affinities={"defend": 0.30, "explore": 0.20},
    ),
    ("BEASTHUMAN", "CAT_KIN"): RaceProfile(
        race_id="BEASTHUMAN",
        sub_lineage="CAT_KIN",
        patron_godmother_slot="gm_beasthuman",
        base_max_health=90.0,
        lifespan_multiplier=1.0,
        gestation_days=1.2,
        breeding_cooldown_mult=1.1,
        neuroplasticity_mult=1.05,
        winter_resistance=1.05,
        movement_speed_mult=1.20,
        adult_scale_height=0.98,
        adult_scale_width=0.98,
        trait_priors={"sociability": 0.10, "caution": 0.05},
        skill_affinities={"forage": 0.20, "scout": 0.20},
    ),
    ("BEASTHUMAN", "DWARF"): RaceProfile(
        race_id="BEASTHUMAN",
        sub_lineage="DWARF",
        patron_godmother_slot="gm_beasthuman",
        base_max_health=125.0,
        lifespan_multiplier=1.5,
        gestation_days=2.2,
        breeding_cooldown_mult=1.4,
        neuroplasticity_mult=0.95,
        winter_resistance=1.60,
        movement_speed_mult=0.95,
        adult_scale_height=0.75,
        adult_scale_width=1.15,
        trait_priors={"rule_respect": 0.25, "loyalty": 0.30},
        skill_affinities={"mine_stone": 0.35, "craft": 0.35, "build": 0.25},
    ),
    ("BEASTHUMAN", "WOLF_KIN"): RaceProfile(
        race_id="BEASTHUMAN",
        sub_lineage="WOLF_KIN",
        patron_godmother_slot="gm_beasthuman",
        base_max_health=115.0,
        lifespan_multiplier=1.1,
        gestation_days=1.4,
        breeding_cooldown_mult=1.1,
        neuroplasticity_mult=1.00,
        winter_resistance=1.35,
        movement_speed_mult=1.12,
        adult_scale_height=1.02,
        adult_scale_width=1.00,
        trait_priors={"loyalty": 0.35, "sociability": 0.20},
        skill_affinities={"scout": 0.25, "defend": 0.20},
    ),
    ("BEASTHUMAN", "BARBARIAN"): RaceProfile(
        race_id="BEASTHUMAN",
        sub_lineage="BARBARIAN",
        patron_godmother_slot="gm_beasthuman",
        base_max_health=145.0,
        lifespan_multiplier=1.1,
        gestation_days=1.8,
        breeding_cooldown_mult=1.2,
        neuroplasticity_mult=0.95,
        winter_resistance=1.45,
        movement_speed_mult=1.0,
        adult_scale_height=1.18,
        adult_scale_width=1.25,
        trait_priors={"loyalty": 0.25, "caution": -0.10},
        skill_affinities={"defend": 0.25, "forage": 0.15},
    ),
    ("BEASTHUMAN", "BEAR_KIN"): RaceProfile(
        race_id="BEASTHUMAN",
        sub_lineage="BEAR_KIN",
        patron_godmother_slot="gm_beasthuman",
        base_max_health=145.0,
        lifespan_multiplier=1.1,
        gestation_days=1.8,
        breeding_cooldown_mult=1.2,
        neuroplasticity_mult=0.95,
        winter_resistance=1.45,
        movement_speed_mult=1.0,
        adult_scale_height=1.18,
        adult_scale_width=1.25,
        trait_priors={"loyalty": 0.25, "caution": -0.10},
        skill_affinities={"defend": 0.25, "forage": 0.15},
    ),
    ("DEMON", None): RaceProfile(
        race_id="DEMON",
        sub_lineage=None,
        patron_godmother_slot="gm_demon",
        base_max_health=120.0,
        lifespan_multiplier=2.8,
        gestation_days=4.0,
        breeding_cooldown_mult=2.2,
        neuroplasticity_mult=1.05,
        winter_resistance=1.50,
        movement_speed_mult=1.05,
        adult_scale_height=1.08,
        adult_scale_width=1.02,
        trait_priors={
            "out_group_aggression": 0.35,
            "dragon_deterrence_bias": 0.65,
            "loyalty": 0.25,
            "ambition": 0.30,
            "rule_respect": -0.05,
        },
        skill_affinities={"craft": 0.25, "defend": 0.25, "trade": 0.10},
    ),
}

# Add convenience string lookups for base races
RACE_REGISTRY["HUMAN"] = RACE_REGISTRY[("HUMAN", None)]
RACE_REGISTRY["ELF"] = RACE_REGISTRY[("ELF", None)]
RACE_REGISTRY["DRAGON"] = RACE_REGISTRY[("DRAGON", None)]
RACE_REGISTRY["BEASTHUMAN"] = RACE_REGISTRY[("BEASTHUMAN", "CAT_KIN")]
RACE_REGISTRY["DEMON"] = RACE_REGISTRY[("DEMON", None)]


def get_race_profile(
    race: RaceId | str,
    sub_lineage: BeasthumanSubLineage | None = None,
) -> RaceProfile:
    """Fetches the corresponding RaceProfile from the registry."""
    valid_races = {"HUMAN", "ELF", "DRAGON", "BEASTHUMAN", "DEMON"}
    r_id: RaceId = cast(RaceId, race) if race in valid_races else "HUMAN"
    key = (r_id, sub_lineage)
    if key in RACE_REGISTRY:
        return RACE_REGISTRY[key]
    if (r_id, None) in RACE_REGISTRY:
        return RACE_REGISTRY[(r_id, None)]
    if r_id in RACE_REGISTRY:
        return RACE_REGISTRY[r_id]
    # Fallback to default sub-lineage or base race
    if r_id == "BEASTHUMAN":
        return RACE_REGISTRY[("BEASTHUMAN", "CAT_KIN")]
    return RACE_REGISTRY[("HUMAN", None)]
