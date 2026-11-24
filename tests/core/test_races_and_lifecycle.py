"""
tests/core/test_races_and_lifecycle.py
5-race biological invariants, cross-species mating & pregnancy, Dragon metamorphosis,
infant crying & distress, developmental age gates, cultural naming, and live birth delivery.
"""

from __future__ import annotations

import random

import numpy as np
import pytest

from sim_core.brains.personality import PersonalityVector, generate_personality_vector
from sim_core.engine import SimulationEngine
from sim_core.lifecycle import LifecycleManager
from sim_core.races import BeasthumanSubLineage, get_race_profile
from sim_core.schemas import AgentRecord, Gender, RaceId, RacialGodMotherSlot, Vec3
from sim_core.society.morality import MoralityEngine
from sim_core.society.naming import (
    generate_birth_name,
    inherit_dynasty_surname,
)
from sim_core.society.religion import get_agent_devotion
from sim_core.society.rumors import RumorNetwork


def _create_adult(
    agent_id: str,
    gender: Gender,
    race: RaceId,
    sub_lineage: BeasthumanSubLineage | None = None,
) -> AgentRecord:
    profile = get_race_profile(race, sub_lineage)
    return AgentRecord(
        agent_id=agent_id,
        slot_idx=0,
        display_name=f"Agent {agent_id}",
        dynasty_surname="TestDynasty",
        gender=gender,
        race=race,
        sub_lineage=sub_lineage,
        dragon_form="HUMANOID_DRAGON" if race == "DRAGON" else None,
        patron_godmother_slot=None,
        stage="ADULT",
        age_ticks=int(6.0 * profile.lifespan_multiplier * 10800),
        health=profile.base_max_health,
        max_health=profile.base_max_health,
        hunger=100.0,
        stamina=100.0,
        pos=Vec3(x=0.0, y=0.0, z=0.0),
    )


def _create_child(
    agent_id: str,
    dominant_race: RaceId,
    secondary_race: RaceId,
    age_days: float = 1.0,
) -> AgentRecord:
    return AgentRecord(
        agent_id=agent_id,
        slot_idx=0,
        display_name=f"Child {agent_id}",
        dynasty_surname="Silverwood",
        gender="BOY",
        race=dominant_race,
        secondary_heritage_race=secondary_race,
        patron_godmother_slot=None,
        godmother_affinities={},
        stage="CHILD",
        age_ticks=int(age_days * 10800),
        health=70.0,
        max_health=70.0,
        hunger=100.0,
        stamina=100.0,
        pos=Vec3(x=0.0, y=0.0, z=0.0),
    )


@pytest.mark.slow
def test_cross_species_1000_pairings_empirical_conception_and_survival() -> None:
    """
    Across 1,000 seeded cross-species pairings: conception ~50%, gestation matches
    mother, survival ~60%.
    """
    pairings: list[tuple[RaceId, RaceId]] = [
        ("HUMAN", "ELF"),
        ("ELF", "BEASTHUMAN"),
        ("BEASTHUMAN", "DRAGON"),
        ("DRAGON", "DEMON"),
        ("DEMON", "HUMAN"),
        ("HUMAN", "BEASTHUMAN"),
    ]

    conceptions = 0
    survivals = 0
    stillbirths = 0

    rng = random.Random(42)

    for i in range(1000):
        race_father, race_mother = pairings[i % len(pairings)]
        father = _create_adult(f"f_{i}", "BOY", race_father)
        mother = _create_adult(f"m_{i}", "GIRL", race_mother)

        seed = rng.randint(0, 1_000_000)
        success, _reason, meta = LifecycleManager.attempt_mating(
            father, mother, current_tick=i * 100, rng_seed=seed
        )

        if success:
            conceptions += 1
            expected_days = get_race_profile(race_mother).gestation_days
            assert meta["gestation_days"] == expected_days
            assert mother.pregnant_ticks_remaining == int(expected_days * 10800)

            birth_seed = rng.randint(0, 1_000_000)
            survived, child, birth_reason = LifecycleManager.deliver_child(
                mother,
                father,
                current_tick=i * 100 + int(expected_days * 10800),
                rng_seed=birth_seed,
            )

            if survived:
                survivals += 1
                assert child is not None
                assert child.stage == "INFANT"
                assert child.patron_godmother_slot is None
                assert child.secondary_heritage_race is not None
            else:
                stillbirths += 1
                assert child is None
                assert birth_reason == "BIRTH_COMPLICATION"

    conception_rate = conceptions / 1000.0
    survival_rate = survivals / float(conceptions)

    assert 0.46 <= conception_rate <= 0.54
    assert 0.55 <= survival_rate <= 0.65
    assert stillbirths + survivals == conceptions


def test_provoked_dragon_metamorphosis_and_rumor_propagation() -> None:
    """Provoked dragon shifts to TRUE_DRAGON, emits 40m fear aura, reverts when calm/exhausted."""
    dragon = _create_adult("dragon_1", "BOY", "DRAGON")
    raider = _create_adult("raider_1", "BOY", "HUMAN")
    witness = _create_adult("witness_1", "GIRL", "HUMAN")
    witness.pos = Vec3(x=5.0, y=0.0, z=0.0)

    morality = MoralityEngine()
    rumors = RumorNetwork()

    morality.record_attack(
        attacker_id=raider.agent_id, victim_id=dragon.agent_id, tick=100, x=0.0, z=0.0
    )
    combat_ctx = morality.classify_combat_context(
        actor_id=dragon.agent_id,
        target_id=raider.agent_id,
        current_tick=105,
        is_active_war=False,
    )
    assert combat_ctx == "SELF_DEFENSE"

    shifted = LifecycleManager.trigger_dragon_metamorphosis(dragon)
    assert shifted is True
    assert dragon.dragon_form == "TRUE_DRAGON"
    assert dragon.max_health == 650.0

    # Stamina drains at 1.8x (0.09) in TRUE_DRAGON form
    initial_stamina = dragon.stamina
    LifecycleManager.advance_agent_tick(
        dragon, current_tick=106, season="SPRING", nearby_threat=True
    )
    stamina_drain = initial_stamina - dragon.stamina
    assert round(stamina_drain, 2) == 0.09

    # Infant reacts to true dragon fear aura (+0.08 distress)
    infant = _create_adult("infant_1", "GIRL", "HUMAN")
    infant.stage = "INFANT"
    infant.distress = 0.20
    LifecycleManager.advance_agent_tick(
        infant,
        current_tick=106,
        season="SPRING",
        true_dragon_aura_nearby=True,
        nearest_parent_dist=2.0,
    )
    assert round(infant.distress, 2) == 0.28

    # Auto-reversion when stamina < 15%
    dragon.stamina = 14.0
    LifecycleManager.advance_agent_tick(
        dragon, current_tick=107, season="SPRING", nearby_threat=False
    )
    assert dragon.dragon_form == "HUMANOID_DRAGON"
    assert dragon.max_health == 280.0

    # Witness propagates rumor
    rumor = rumors.spawn_rumor(
        topic="DRAGON_METAMORPHOSIS",
        content="A True Dragon leveled the raiders at Ashpeak sanctuary!",
        origin_tick=105,
        origin_parcel="0_0",
        salience=0.95,
        witness_ids=[witness.agent_id],
    )
    assert rumor.credibility == 1.0

    citizen = _create_adult("citizen_2", "BOY", "HUMAN")
    exchanged = rumors.exchange_rumors(
        witness.agent_id, citizen.agent_id, dist_meters=4.0, current_tick=110
    )
    assert exchanged > 0
    citizen_rumors = rumors.get_agent_rumors(citizen.agent_id, current_tick=110)
    assert len(citizen_rumors) == 1
    assert round(citizen_rumors[0].credibility, 2) == 0.90


def test_dragon_mating_constraint() -> None:
    """Dragons must be in HUMANOID_DRAGON form when mating."""
    dragon = _create_adult("dragon_m", "BOY", "DRAGON")
    elf = _create_adult("elf_f", "GIRL", "ELF")

    LifecycleManager.trigger_dragon_metamorphosis(dragon)
    assert dragon.dragon_form == "TRUE_DRAGON"

    success, reason, _ = LifecycleManager.attempt_mating(dragon, elf, current_tick=100)
    assert success is False
    assert "TRUE_DRAGON_MATING_FORBIDDEN" in reason

    LifecycleManager.revert_dragon_metamorphosis(dragon)
    assert dragon.dragon_form == "HUMANOID_DRAGON"
    success2, reason2, _ = LifecycleManager.attempt_mating(
        dragon, elf, current_tick=100, rng_seed=42
    )
    assert "TRUE_DRAGON_MATING_FORBIDDEN" not in reason2


def test_demon_race_reproduction_temperament_and_dragon_deterrence() -> None:
    """Verifies Demon race reproduction, temperament priors, and generational Dragon deterrence."""
    profile = get_race_profile("DEMON")
    assert profile.lifespan_multiplier == 2.8
    assert profile.gestation_days == 4.0
    assert profile.base_max_health == 120.0
    assert profile.winter_resistance == 1.50
    assert profile.patron_godmother_slot == "gm_demon"
    assert profile.trait_priors["out_group_aggression"] == 0.35
    assert profile.trait_priors["dragon_deterrence_bias"] == 0.65

    # Same-gender mating forbidden
    demon_boy1 = _create_adult("db1", "BOY", "DEMON")
    demon_boy2 = _create_adult("db2", "BOY", "DEMON")
    success, reason, _ = LifecycleManager.attempt_mating(demon_boy1, demon_boy2, current_tick=100)
    assert success is False
    assert "SAME_GENDER_MATING_FORBIDDEN" in reason

    # Mother-race gestation durations
    elf_mother = _create_adult("em1", "GIRL", "ELF")
    succ_elf, _, meta_elf = LifecycleManager.attempt_mating(
        demon_boy1, elf_mother, current_tick=100, rng_seed=42
    )
    if succ_elf:
        assert meta_elf["gestation_days"] == 3.0

    human_father = _create_adult("hf1", "BOY", "HUMAN")
    demon_mother = _create_adult("dm1", "GIRL", "DEMON")
    succ_demon, _, meta_demon = LifecycleManager.attempt_mating(
        human_father, demon_mother, current_tick=100, rng_seed=42
    )
    if succ_demon:
        assert meta_demon["gestation_days"] == 4.0

    # Morality: unprovoked attack on Dragon inhibited by generational deterrence
    morality = MoralityEngine()
    demon_traits = {"out_group_aggression": 0.40, "dragon_deterrence_bias": 0.70}
    assert morality.evaluate_attack_inhibited(
        "DEMON", "DRAGON", demon_traits, is_self_defense=False
    )
    assert not morality.evaluate_attack_inhibited(
        "DEMON", "DRAGON", demon_traits, is_self_defense=True
    )
    assert not morality.evaluate_attack_inhibited(
        "DEMON", "HUMAN", demon_traits, is_self_defense=False
    )

    f_human = morality.compute_racial_friction_modifier("DEMON", "HUMAN", demon_traits)
    f_dragon = morality.compute_racial_friction_modifier("DEMON", "DRAGON", demon_traits)
    assert f_dragon < f_human


def test_demon_generational_dragon_deterrence_and_individual_variation() -> None:
    """Demon agents inherit out-group aggression and Dragon deterrence with Gaussian variation."""
    demon_samples = [generate_personality_vector("DEMON") for _ in range(100)]
    human_samples = [generate_personality_vector("HUMAN") for _ in range(100)]

    avg_demon_outgroup = sum(p.out_group_trust for p in demon_samples) / 100.0
    avg_human_outgroup = sum(p.out_group_trust for p in human_samples) / 100.0
    avg_demon_caution = sum(p.caution for p in demon_samples) / 100.0
    avg_demon_devotion = sum(p.devotion for p in demon_samples) / 100.0

    assert avg_demon_outgroup < avg_human_outgroup
    assert avg_demon_caution >= 0.65
    assert avg_demon_devotion >= 0.70
    assert np.std([p.caution for p in demon_samples]) > 0.01


@pytest.mark.parametrize(
    (
        "dom_race",
        "sec_race",
        "age_days",
        "voluntary",
        "affinities",
        "goddess_decision",
        "expected_status",
        "expected_slot",
    ),
    [
        ("HUMAN", "ELF", 2.0, None, {}, None, None, None),  # Under age 10
        ("HUMAN", "ELF", 3.4, "gm_elf", {}, None, "VOLUNTARY_CHOICE_LOCKED", "gm_elf"),
        (
            "HUMAN",
            "ELF",
            3.4,
            None,
            {"gm_human": 0.85, "gm_elf": 0.40},
            None,
            "AUTO_ALLOCATED_HIGHER_AFFINITY",
            "gm_human",
        ),
        (
            "HUMAN",
            "ELF",
            3.4,
            None,
            {"gm_human": 0.50, "gm_elf": 0.50},
            "gm_elf",
            "WORLD_GODDESS_TIE_BREAK_DECREE",
            "gm_elf",
        ),
        ("DEMON", "HUMAN", 10.0, "gm_demon", {}, None, "VOLUNTARY_CHOICE_LOCKED", "gm_demon"),
        (
            "DEMON",
            "HUMAN",
            10.0,
            None,
            {"gm_demon": 0.80, "gm_human": 0.30},
            None,
            "AUTO_ALLOCATED_HIGHER_AFFINITY",
            "gm_demon",
        ),
        (
            "DEMON",
            "HUMAN",
            10.0,
            None,
            {"gm_demon": 0.50, "gm_human": 0.50},
            "gm_demon",
            "WORLD_GODDESS_TIE_BREAK_DECREE",
            "gm_demon",
        ),
    ],
)
def test_mixed_race_child_age10_patronage_choice_and_tie_break(
    dom_race: RaceId,
    sec_race: RaceId,
    age_days: float,
    voluntary: RacialGodMotherSlot | None,
    affinities: dict[str, float],
    goddess_decision: RacialGodMotherSlot | None,
    expected_status: str | None,
    expected_slot: str | None,
) -> None:
    """
    Verifies mixed-race Age-10 patronage choices, auto-allocation, and World Goddess
    tie-breaks.
    """
    child = _create_child("child_age10_test", dom_race, sec_race, age_days=age_days)
    child.godmother_affinities = affinities

    if expected_status is None:
        LifecycleManager.advance_agent_tick(child, current_tick=100)
        assert child.patron_godmother_slot is None
    else:
        res = LifecycleManager.resolve_age10_patronage(
            child, voluntary_choice=voluntary, world_goddess_decision=goddess_decision
        )
        assert expected_status in res
        assert child.patron_godmother_slot == expected_slot


def test_infant_distress_crying_and_gradual_comforting() -> None:
    """Infant distress crosses crying threshold (0.45); comforting reduces distress gradually."""
    infant = AgentRecord(
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
        hunger=40.0,
        distress=0.40,
        crying=False,
        pos=Vec3(x=0.0, y=0.0, z=0.0),
    )
    parent = AgentRecord(
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
        pos=Vec3(x=2.0, y=0.0, z=0.0),
        skills={"teach": 0.5, "self_care": 0.5},
    )

    LifecycleManager.advance_agent_tick(
        infant, current_tick=101, season="SPRING", nearest_parent_dist=2.0
    )
    assert infant.distress >= 0.45
    assert infant.crying is True

    reduction = LifecycleManager.soothe_or_comfort_child(parent, infant, dist_meters=2.0)
    assert 0.06 <= reduction <= 0.10

    # No magic mute button: hunger < 55 pushes infant back to crying
    LifecycleManager.advance_agent_tick(
        infant, current_tick=102, season="SPRING", nearest_parent_dist=2.0
    )
    LifecycleManager.advance_agent_tick(
        infant, current_tick=103, season="SPRING", nearest_parent_dist=2.0
    )
    assert infant.crying is True

    # Resolving root-cause hunger + soothing clears crying
    infant.hunger = 90.0
    LifecycleManager.soothe_or_comfort_child(parent, infant, dist_meters=2.0)
    LifecycleManager.advance_agent_tick(
        infant, current_tick=104, season="SPRING", nearest_parent_dist=2.0
    )
    assert infant.distress < 0.45
    assert infant.crying is False


def test_infant_parent_proximity_distress() -> None:
    """Infant separated from caretaker accumulates distance distress."""
    cared = AgentRecord(
        agent_id="inf_cared",
        slot_idx=0,
        display_name="Cared",
        dynasty_surname="Lineage",
        race="HUMAN",
        gender="BOY",
        stage="INFANT",
        age_ticks=50,
        distress=0.0,
        hunger=90.0,
    )
    alone = AgentRecord(
        agent_id="inf_alone",
        slot_idx=1,
        display_name="Alone",
        dynasty_surname="Lineage",
        race="HUMAN",
        gender="GIRL",
        stage="INFANT",
        age_ticks=50,
        distress=0.0,
        hunger=90.0,
    )

    for _ in range(10):
        LifecycleManager.advance_agent_tick(
            cared, current_tick=100, nearest_parent_dist=2.0, is_sheltered=True
        )
        LifecycleManager.advance_agent_tick(
            alone, current_tick=100, nearest_parent_dist=80.0, is_sheltered=False
        )

    assert cared.distress < alone.distress


def test_cultural_birth_naming_dynasties_and_holy_imprinting() -> None:
    """Newborns receive racial names and dynasties; Holy Nation births imprint faith devotion."""
    elf_boy = generate_birth_name("ELF", "BOY", seed=10)
    elf_girl = generate_birth_name("ELF", "GIRL", seed=10)
    human_boy = generate_birth_name("HUMAN", "BOY", seed=10)
    dragon_girl = generate_birth_name("DRAGON", "GIRL", seed=10)
    dwarf_boy = generate_birth_name("BEASTHUMAN", "BOY", sub_lineage="DWARF", seed=10)

    assert len(elf_boy) >= 3
    assert len(elf_girl) >= 3
    assert len(human_boy) >= 3
    assert len(dragon_girl) >= 3
    assert len(dwarf_boy) >= 3

    inherited = inherit_dynasty_surname("Silverleaf", "Thornwood", "ELF", seed=42)
    assert inherited in ("Silverleaf", "Thornwood")

    mother = _create_adult("mom_holy", "GIRL", "ELF")
    father = _create_adult("dad_holy", "BOY", "ELF")
    mother.traits["faith_devotion"] = 0.8
    father.traits["faith_devotion"] = 0.8

    survived, child, _ = LifecycleManager.deliver_child(
        mother, father, current_tick=1000, rng_seed=42, holy_nation_birth=True
    )
    assert survived is True
    assert child is not None
    assert 0.25 <= child.traits["faith_devotion"] <= 0.45


def test_sub_lineage_profile_lookups() -> None:
    """Specialized sub-lineage profiles configure distinct base stats."""
    dwarf = get_race_profile("BEASTHUMAN", "DWARF")
    assert dwarf.base_max_health == 125.0
    assert dwarf.winter_resistance == 1.60

    barb = get_race_profile("BEASTHUMAN", "BARBARIAN")
    assert barb.base_max_health == 145.0

    cat = get_race_profile("BEASTHUMAN", "CAT_KIN")
    assert cat.base_max_health == 90.0

    assert (
        LifecycleManager.get_max_health_for_stage(
            race="BEASTHUMAN", stage="ADULT", sub_lineage="DWARF"
        )
        == 125.0
    )
    assert (
        LifecycleManager.get_max_health_for_stage(
            race="BEASTHUMAN", stage="ADULT", sub_lineage="CAT_KIN"
        )
        == 90.0
    )


def test_newborn_personality_crossover_and_devotion_sync() -> None:
    """deliver_child() blends parents' personality vector and synchronizes devotion."""
    mother = _create_adult("m1", "GIRL", "HUMAN")
    father = _create_adult("f1", "BOY", "HUMAN")
    mother.personality = PersonalityVector(curiosity=0.9, devotion=0.8)
    father.personality = PersonalityVector(curiosity=0.7, devotion=0.6)

    survived, newborn, _ = LifecycleManager.deliver_child(mother, father, current_tick=100)
    assert survived is True
    assert newborn is not None
    assert newborn.personality is not None
    assert newborn.mood is not None
    assert newborn.mood.calm == 0.8
    assert abs(newborn.traits["faith_devotion"] - newborn.personality.devotion) < 0.005
    assert abs(get_agent_devotion(newborn) - newborn.personality.devotion) < 0.005


def test_live_birth_delivery_in_engine_step_tick(engine: SimulationEngine) -> None:
    """Engine step tick delivers pregnant mother, adds agent, and conserves credits exactly."""
    initial_credits = sum(a.credits for a in engine.agents.values()) + engine.bank.reserve_credits
    mother = engine.spawn_agent(race="HUMAN", gender="GIRL", stage="ADULT", initial_credits=100.0)
    father = engine.spawn_agent(race="HUMAN", gender="BOY", stage="ADULT", initial_credits=100.0)

    mother.pregnant_ticks_remaining = 1
    mother.pregnancy_father_id = father.agent_id
    initial_pop = len(engine.agents)

    engine.step_tick()

    assert len(engine.agents) == initial_pop + 1
    assert mother.pregnant_ticks_remaining == 0
    delivered = [
        a
        for a in engine.agents.values()
        if a.stage == "INFANT" and a.parent_ids == [mother.agent_id, father.agent_id]
    ]
    assert len(delivered) == 1
    newborn = delivered[0]
    assert newborn.credits == 0.0
    assert newborn.slot_idx in engine.batched_net.active_slots

    current_credits = sum(a.credits for a in engine.agents.values()) + engine.bank.reserve_credits
    assert abs(current_credits - initial_credits) < 1e-6


def test_safe_delivery_and_devotion_sync(engine: SimulationEngine) -> None:
    """Dead pregnant mother does not spawn child; live delivery grounds elevation to heightmap."""
    # 1. Mother dies on delivery tick -> perinatal complication, no living infant
    mother_dead = engine.spawn_agent(race="HUMAN", gender="GIRL", stage="ADULT")
    mother_dead.pregnant_ticks_remaining = 1
    mother_dead.health = 0.001
    mother_dead.hunger = 0.0
    initial_alive = engine.judiciary.population_ledger.get("total_alive", 0)

    engine.step_tick()
    assert not mother_dead.alive
    assert engine.judiciary.population_ledger.get("total_alive", 0) == initial_alive - 1
    assert any(f.cause == "BIRTH_COMPLICATION" for f in engine.judiciary.fatalities)

    # 2. Live birth grounds elevation to heightmap
    mother_live = engine.spawn_agent(race="ELF", gender="GIRL", stage="ADULT")
    mother_live.pos = Vec3(x=50.0, y=99.0, z=50.0)
    mother_live.pregnant_ticks_remaining = 1
    mother_live.health = 50.0
    mother_live.hunger = 90.0

    engine.step_tick()
    child = next(
        (a for a in engine.agents.values() if a.alive and mother_live.agent_id in a.parent_ids),
        None,
    )
    assert child is not None
    expected_y = engine.heightmap.get_elevation(child.pos.x, child.pos.z)
    assert abs(child.pos.y - expected_y) < 1e-4


def test_engine_idempotent_despawn() -> None:
    """
    SimulationEngine.despawn_agent is cleanly idempotent and preserves record
    in engine.agents.
    """
    engine = SimulationEngine(headless=True)
    agent = engine.spawn_agent(
        race="HUMAN", gender="BOY", stage="ADULT", pos=Vec3(x=10.0, y=18.0, z=10.0)
    )
    agent_id = agent.agent_id
    slot_idx = agent.slot_idx

    assert agent.alive is True
    assert slot_idx in engine.batched_net.active_slots

    res1 = engine.despawn_agent(agent_id, reason="TEST_DEATH")
    assert res1 is True
    assert agent_id in engine.agents
    assert agent.alive is False
    assert slot_idx in engine.batched_net.free_slots

    res2 = engine.despawn_agent(agent_id, reason="TEST_DEATH")
    assert res2 is False
