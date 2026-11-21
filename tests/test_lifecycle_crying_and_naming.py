"""
tests/test_lifecycle_crying_and_naming.py
Phase 3A Mandatory Acceptance Tests:
- Hungry/injured infant crosses distress >= 0.45 (crying=True); parent comforting
  reduces distress gradually, but infant keeps crying until root causes are resolved.
- Newborns receive racial/gender cultural names + dynasty surnames;
  Holy Nation births apply +0.25..+0.45 faith_devotion birth imprinting.
- Winter scarcity increases hunger decay and lowers wild food regen.
"""

from sim_core.lifecycle import LifecycleManager
from sim_core.schemas import AgentRecord as AgentState
from sim_core.schemas import Vec3
from sim_core.society.naming import (
    generate_birth_name,
    generate_dynasty_surname,
    inherit_dynasty_surname,
)
from sim_core.society.seasons import SeasonManager


def test_infant_distress_crying_and_gradual_comforting():
    """
    Acceptance Requirement:
    - Hungry/injured infant accumulates distress and starts crying at distress >= 0.45.
    - Parent comforting reduces distress gradually by -0.06 to -0.10 per tick.
    - Infant keeps crying while root cause (hunger < 55) persists (no magic mute button).
    """
    infant = AgentState(
        agent_id="infant_test",
        slot_idx=0,
        display_name="Mira Thornwood",
        dynasty_surname="Thornwood",
        gender="GIRL",
        race="HUMAN",
        stage="INFANT",
        age_ticks=100,
        health=40.0,
        max_health=40.0,
        hunger=40.0,  # Unfed hunger < 55 triggers root-cause distress
        stamina=100.0,
        distress=0.40,
        crying=False,
        pos=Vec3(x=0.0, y=0.0, z=0.0),
    )

    parent = AgentState(
        agent_id="parent_test",
        slot_idx=1,
        display_name="Aldric Thornwood",
        dynasty_surname="Thornwood",
        gender="BOY",
        race="HUMAN",
        stage="ADULT",
        age_ticks=100000,
        health=100.0,
        max_health=100.0,
        hunger=100.0,
        stamina=100.0,
        pos=Vec3(x=2.0, y=0.0, z=0.0),  # within 4m comforting range
        skills={"teach": 0.5, "self_care": 0.5},
    )

    # 1. Advance tick: Unfed infant distress increases (+0.05) and crosses crying threshold (0.45)
    LifecycleManager.advance_agent_tick(
        infant,
        current_tick=101,
        season="SPRING",
        nearest_parent_dist=2.0,
    )
    assert infant.distress >= 0.45
    assert infant.crying is True, "Infant must be crying when distress >= 0.45"

    # 2. Parent comforts infant gradually
    reduction = LifecycleManager.soothe_or_comfort_child(parent, infant, dist_meters=2.0)
    assert 0.06 <= reduction <= 0.10, f"Comforting reduction {reduction} outside [0.06, 0.10]"

    # 3. No Magic Mute Button: If parent doesn't feed infant (hunger < 55 persists),
    # persistent distress pushes child back across threshold into crying
    LifecycleManager.advance_agent_tick(
        infant,
        current_tick=102,
        season="SPRING",
        nearest_parent_dist=2.0,
    )
    LifecycleManager.advance_agent_tick(
        infant,
        current_tick=103,
        season="SPRING",
        nearest_parent_dist=2.0,
    )
    assert infant.hunger < 55.0
    # Because hunger was not solved, distress rises back across 0.45 and crying resumes
    assert infant.distress >= 0.45
    assert infant.crying is True, "Infant must resume crying while root-cause hunger persists"

    # 4. Now feed infant and resolve root cause
    infant.hunger = 90.0
    # Comfort child again down below threshold
    LifecycleManager.soothe_or_comfort_child(parent, infant, dist_meters=2.0)
    LifecycleManager.advance_agent_tick(
        infant,
        current_tick=104,
        season="SPRING",
        nearest_parent_dist=2.0,
    )
    assert infant.distress < 0.45
    assert infant.crying is False, "Infant stops crying once hunger and distress are resolved"


def test_cultural_birth_naming_dynasties_and_holy_imprinting():
    """
    Acceptance Requirement:
    - Newborns receive racial/gender cultural names + dynasty surnames.
    - Holy Nation births apply +0.25..+0.45 faith_devotion birth imprinting.
    """
    # 1. Phoneme birth naming
    elf_boy = generate_birth_name("ELF", "BOY", seed=10)
    elf_girl = generate_birth_name("ELF", "GIRL", seed=10)
    human_boy = generate_birth_name("HUMAN", "BOY", seed=10)
    dragon_girl = generate_birth_name("DRAGON", "GIRL", seed=10)
    dwarf_boy = generate_birth_name("BEASTHUMAN", "BOY", sub_lineage="DWARF", seed=10)

    assert elf_boy in [
        "Aelarion", "Faelar", "Sylas", "Thalor", "Elenion", "Caelynn", "Lorian", "Ilidor", "Aerin"
    ]
    assert elf_girl in [
        "Lyra", "Aeris", "Eleniel", "Vaeloria", "Naevys", "Althea", "Sylphira", "Fiora", "Ilyria"
    ]
    assert human_boy in [
        "Aldric", "Kaelen", "Cedric", "Lucian", "Valen", "Gareth", "Rowan", "Tristan",
        "Edwin", "Thomas", "Roger"
    ]
    assert "Pyra" in dragon_girl or "Cinder" in dragon_girl or len(dragon_girl) > 3
    assert dwarf_boy in [
        "Torin", "Brokk", "Duer", "Thrain", "Gimli", "Berta", "Balin", "Durin", "Thrum"
    ]

    # 2. Dynasty inheritance
    inherited = inherit_dynasty_surname("Silverleaf", "Thornwood", "ELF", seed=42)
    assert inherited in ("Silverleaf", "Thornwood")

    founder_dynasty = generate_dynasty_surname("DRAGON", seed=42)
    assert len(founder_dynasty) > 3

    # 3. Holy Nation Birth Imprinting
    mother = AgentState(
        agent_id="mom_holy",
        slot_idx=0,
        display_name="Lyra Moonwhisper",
        dynasty_surname="Moonwhisper",
        gender="GIRL",
        race="ELF",
        stage="ADULT",
        age_ticks=200000,
        health=95.0,
        max_health=95.0,
        hunger=100.0,
        stamina=100.0,
        pos=Vec3(x=0.0, y=0.0, z=0.0),
        traits={"faith_devotion": 0.8},
    )
    father = AgentState(
        agent_id="dad_holy",
        slot_idx=1,
        display_name="Aelarion Moonwhisper",
        dynasty_surname="Moonwhisper",
        gender="BOY",
        race="ELF",
        stage="ADULT",
        age_ticks=200000,
        health=95.0,
        max_health=95.0,
        hunger=100.0,
        stamina=100.0,
        pos=Vec3(x=0.0, y=0.0, z=0.0),
        traits={"faith_devotion": 0.8},
    )

    survived, child, reason = LifecycleManager.deliver_child(
        mother, father, current_tick=1000, rng_seed=42, holy_nation_birth=True
    )
    assert survived is True
    assert child is not None
    assert 0.25 <= child.traits["faith_devotion"] <= 0.45, (
        f"Holy Nation birth must imprint +0.25..+0.45 faith, got {child.traits['faith_devotion']}"
    )


def test_winter_scarcity_multipliers():
    """
    Acceptance Requirement:
    - Winter increases hunger decay (1.6x base, 2.2x unsheltered infant,
      attenuated by winter_resistance).
    - Wild food regen is 0.4x in Winter (-60%) vs 1.3x in Autumn and 1.2x in Spring.
    """
    # 1. Hunger decay
    h_spring = SeasonManager.get_hunger_multiplier("SPRING")
    h_winter = SeasonManager.get_hunger_multiplier("WINTER")
    assert h_spring == 1.0
    assert h_winter == 1.6

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

    # 2. Wild food regen
    assert SeasonManager.get_wild_food_multiplier("SPRING") == 1.2
    assert SeasonManager.get_wild_food_multiplier("SUMMER") == 1.0
    assert SeasonManager.get_wild_food_multiplier("AUTUMN") == 1.3
    assert SeasonManager.get_wild_food_multiplier("WINTER") == 0.4
