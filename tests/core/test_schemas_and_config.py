"""
tests/core/test_schemas_and_config.py
Core schema validation, configuration constants, biological aging milestones,
winter scarcity multipliers, and morning boot pacing.
"""

from __future__ import annotations

import pytest

from sim_core.config import (
    ADULT_BIOLOGICAL_YEARS,
    AGE_10_BIOLOGICAL_YEARS,
    TICKS_PER_GAME_DAY,
    calculate_biological_age_years,
)
from sim_core.engine import SimulationEngine
from sim_core.races import (
    CROSS_SPECIES_BIRTH_SURVIVAL_CHANCE,
    CROSS_SPECIES_CONCEPTION_CHANCE,
    RACE_REGISTRY,
    get_race_profile,
)
from sim_core.schemas import (
    AgentRecord,
    DailyManifest,
    DivineEntityRecord,
    DivinePersonality,
    SisterCouncilMessage,
    Vec3,
)
from sim_core.society.seasons import SeasonManager


def test_race_registry_and_constants() -> None:
    """Verifies all 5 races, sub-lineages, and cross-species probability invariants."""
    assert CROSS_SPECIES_CONCEPTION_CHANCE == 0.50
    assert CROSS_SPECIES_BIRTH_SURVIVAL_CHANCE == 0.60

    human_prof = get_race_profile("HUMAN")
    assert human_prof.race_id == "HUMAN"
    assert human_prof.lifespan_multiplier == 1.0
    assert human_prof.gestation_days == 1.5
    assert human_prof.neuroplasticity_mult == 1.15

    elf_prof = get_race_profile("ELF")
    assert elf_prof.race_id == "ELF"
    assert elf_prof.lifespan_multiplier == 3.0
    assert elf_prof.gestation_days == 4.0

    dragon_prof = get_race_profile("DRAGON")
    assert dragon_prof.race_id == "DRAGON"
    assert dragon_prof.lifespan_multiplier == 6.0
    assert dragon_prof.gestation_days == 7.0
    assert dragon_prof.can_metamorphose is True
    assert dragon_prof.true_dragon_health == 650.0

    demon_prof = get_race_profile("DEMON")
    assert demon_prof.race_id == "DEMON"
    assert demon_prof.lifespan_multiplier == 2.8
    assert demon_prof.gestation_days == 4.0
    assert demon_prof.base_max_health == 120.0
    assert demon_prof.winter_resistance == 1.50
    assert demon_prof.patron_godmother_slot == "gm_demon"

    cat_prof = get_race_profile("BEASTHUMAN", "CAT_KIN")
    assert cat_prof.race_id == "BEASTHUMAN"
    assert cat_prof.sub_lineage == "CAT_KIN"
    assert cat_prof.gestation_days == 1.2

    dwarf_prof = get_race_profile("BEASTHUMAN", "DWARF")
    assert dwarf_prof.race_id == "BEASTHUMAN"
    assert dwarf_prof.sub_lineage == "DWARF"
    assert dwarf_prof.gestation_days == 2.2
    assert dwarf_prof.winter_resistance == 1.60

    assert len(RACE_REGISTRY) >= 8


@pytest.mark.parametrize(
    ("race_id", "lifespan_mult"),
    [
        ("HUMAN", 1.0),
        ("ELF", 3.0),
        ("DRAGON", 6.0),
        ("DEMON", 2.8),
    ],
)
def test_biological_age_formula(race_id: str, lifespan_mult: float) -> None:
    """Verifies adult stage gate at (6.0 * L) and age 10 milestone at (3.33 * L) game days."""
    adult_days = 6.0 * lifespan_mult
    bio_adult = calculate_biological_age_years(adult_days, lifespan_mult)
    assert bio_adult == pytest.approx(ADULT_BIOLOGICAL_YEARS, abs=1e-4)

    age_10_days = (10.0 / 3.0) * lifespan_mult
    bio_10 = calculate_biological_age_years(age_10_days, lifespan_mult)
    assert bio_10 == pytest.approx(AGE_10_BIOLOGICAL_YEARS, abs=1e-2)


def test_schemas_instantiation_and_validation() -> None:
    """Verifies core Pydantic v2 domain schemas."""
    agent = AgentRecord(
        agent_id="agt_0001",
        slot_idx=0,
        display_name="Aiden",
        dynasty_surname="Vanguard",
        gender="BOY",
        race="HUMAN",
        pos=Vec3(x=16.5, y=10.0, z=-32.0),
    )
    assert agent.gender == "BOY"
    assert agent.stage == "INFANT"
    assert agent.crying is False
    assert agent.credits == 10.0

    deity = DivineEntityRecord(
        slot="gm_human",
        bestowed_name="Solis",
        role="RACIAL_GOD_MOTHER",
        patron_race="HUMAN",
        personality=DivinePersonality(compassion=0.7, restraint=0.5),
    )
    assert deity.bestowed_name == "Solis"
    assert deity.divine_energy == 300.0

    council_msg = SisterCouncilMessage(
        message_id="msg_001",
        day=1,
        tick=120,
        sender_slot="gm_human",
        recipient_slots=["gm_elf"],
        topic="BORDER_FRICTION",
        summary="Human settlers foraging near Sylvan border.",
    )
    assert council_msg.topic == "BORDER_FRICTION"

    manifest = DailyManifest(
        day=1,
        tick=10800,
        season="SPRING",
        committed_by="Gaia",
        db_path="data/civilization.db",
        db_sha256="dummy_db_sha256",
        pt_path="data/checkpoints/day_00001.pt",
        pt_sha256="dummy_pt_sha256",
        ledger_path="data/god_ledger/day_00001.md",
        status="VERIFIED",
    )
    assert manifest.status == "VERIFIED"


def test_winter_scarcity_multipliers() -> None:
    """Verifies hunger decay and wild food regen scaling across seasons."""
    assert SeasonManager.get_hunger_multiplier("SPRING") == 1.0
    assert SeasonManager.get_hunger_multiplier("WINTER") == 1.6

    # Unsheltered infant in Winter
    h_infant_winter = SeasonManager.get_hunger_multiplier(
        "WINTER", is_infant=True, is_sheltered=False, winter_resistance=1.0
    )
    assert h_infant_winter == 2.2

    # Dragon Winter resistance (1.80x) attenuates hunger decay
    h_dragon_winter = SeasonManager.get_hunger_multiplier(
        "WINTER", is_infant=False, is_sheltered=False, winter_resistance=1.80
    )
    assert round(h_dragon_winter, 3) == round(1.6 / 1.80, 3)

    # Wild food regen
    assert SeasonManager.get_wild_food_multiplier("SPRING") == 1.2
    assert SeasonManager.get_wild_food_multiplier("SUMMER") == 1.0
    assert SeasonManager.get_wild_food_multiplier("AUTUMN") == 1.3
    assert SeasonManager.get_wild_food_multiplier("WINTER") == 0.4


def test_engine_boots_at_golden_morning(engine: SimulationEngine) -> None:
    """Verifies engine boots at golden morning 08:30 and syncs weather time."""
    assert engine.day_start_hour == 8.5
    engine.step_tick()
    engine.step_tick()  # sync_weather_time fires on even ticks
    wt = engine.adapter.weather_time  # type: ignore[attr-defined]
    expected = (2 / float(TICKS_PER_GAME_DAY)) * 24.0 + 8.5
    assert wt["time_of_day"] == pytest.approx(expected, abs=1e-6)
    assert 8.5 <= wt["time_of_day"] < 8.6
