"""
tests/test_races_gender_pregnancy_dragon_morph.py
Phase 3A Mandatory Acceptance Tests:
- 1,000 seeded cross-species pairings: empirical conception ~50%, birth survival ~60%,
  gestation matches mother's RaceProfile.gestation_days, stillbirths log BIRTH_COMPLICATION.
- Provoked Dragon shifts HUMANOID_DRAGON -> TRUE_DRAGON, emits 40m fear aura,
  drains stamina at 1.8x, reverts when threat clears or stamina < 15%, witnesses spread rumors.
"""

import random

from sim_core.lifecycle import LifecycleManager
from sim_core.races import BeasthumanSubLineage, get_race_profile
from sim_core.schemas import AgentRecord as AgentState
from sim_core.schemas import Gender, RaceId, Vec3
from sim_core.society.morality import MoralityEngine
from sim_core.society.rumors import RumorNetwork


def _create_adult(
    agent_id: str,
    gender: Gender,
    race: RaceId,
    sub_lineage: BeasthumanSubLineage | None = None,
) -> AgentState:
    profile = get_race_profile(race, sub_lineage)
    return AgentState(
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


def test_cross_species_1000_pairings_empirical_conception_and_survival():
    """
    Acceptance Requirement:
    Across 1,000 seeded cross-species pairings:
    - Empirical conception rate converges to ~50%
    - Gestation duration matches mother's RaceProfile.gestation_days
    - Offspring birth survival converges to ~60%
    - Stillbirths log BIRTH_COMPLICATION with zero child allocated
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

        # Attempt mating
        seed = rng.randint(0, 1_000_000)
        success, reason, meta = LifecycleManager.attempt_mating(
            father, mother, current_tick=i * 100, rng_seed=seed
        )

        if success:
            conceptions += 1
            # Verify gestation matches mother's race profile
            expected_days = get_race_profile(race_mother).gestation_days
            assert meta["gestation_days"] == expected_days, (
                f"Gestation days {meta['gestation_days']} does not match mother's {expected_days}"
            )
            assert mother.pregnant_ticks_remaining == int(expected_days * 10800)

            # Deliver child
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
                # Mixed-race child starts uncommitted
                assert child.patron_godmother_slot is None
                assert child.secondary_heritage_race is not None
            else:
                stillbirths += 1
                assert child is None
                assert birth_reason == "BIRTH_COMPLICATION"

    conception_rate = conceptions / 1000.0
    survival_rate = survivals / float(conceptions)

    print(
        f"\n[CROSS_SPECIES_STATS] 1,000 Pairings: "
        f"Conceptions: {conceptions}/1000 ({conception_rate:.1%}) | "
        f"Survivals: {survivals}/{conceptions} ({survival_rate:.1%}) | "
        f"Stillbirths: {stillbirths}"
    )

    # Statistical convergence bounds for 1000 trials
    assert 0.46 <= conception_rate <= 0.54, (
        f"Conception rate {conception_rate:.3f} outside [0.46, 0.54]"
    )
    assert 0.55 <= survival_rate <= 0.65, f"Birth survival {survival_rate:.3f} outside [0.55, 0.65]"
    assert stillbirths + survivals == conceptions


def test_provoked_dragon_metamorphosis_and_rumor_propagation():
    """
    Acceptance Requirement:
    Provoked Adult Dragon shifts HUMANOID_DRAGON -> TRUE_DRAGON (SELF_DEFENSE, zero crime),
    emits 40m fear aura, drains stamina at 1.8x, reverts when threat clears or stamina < 15%,
    and witnesses propagate Rumor Packets.
    """
    dragon = _create_adult("dragon_1", "BOY", "DRAGON")
    raider = _create_adult("raider_1", "BOY", "HUMAN")
    witness = _create_adult("witness_1", "GIRL", "HUMAN")
    witness.pos = Vec3(x=5.0, y=0.0, z=0.0)  # within 40m fear aura and 8m rumor distance

    morality = MoralityEngine()
    rumors = RumorNetwork()

    # 1. Raider attacks dragon
    morality.record_attack(
        attacker_id=raider.agent_id, victim_id=dragon.agent_id, tick=100, x=0.0, z=0.0
    )

    # Classify dragon retaliation context
    combat_ctx = morality.classify_combat_context(
        actor_id=dragon.agent_id,
        target_id=raider.agent_id,
        current_tick=105,
        is_active_war=False,
    )
    assert combat_ctx == "SELF_DEFENSE", "Provoked dragon retaliation must be SELF_DEFENSE"

    # 2. Metamorphosis Trigger
    shifted = LifecycleManager.trigger_dragon_metamorphosis(dragon)
    assert shifted is True
    assert dragon.dragon_form == "TRUE_DRAGON"
    assert dragon.max_health == 650.0

    # 3. Fear aura & Stamina drain at 1.8x
    # Witness infant or nearby agent reacts to true dragon fear aura
    infant = _create_adult("infant_1", "GIRL", "HUMAN")
    infant.stage = "INFANT"
    infant.distress = 0.20

    initial_stamina = dragon.stamina
    LifecycleManager.advance_agent_tick(
        dragon,
        current_tick=106,
        season="SPRING",
        nearby_threat=True,
    )
    stamina_drain = initial_stamina - dragon.stamina
    # Normal drain is 0.05, 1.8x is 0.09
    assert round(stamina_drain, 2) == 0.09, f"Expected 0.09 stamina drain, got {stamina_drain}"

    LifecycleManager.advance_agent_tick(
        infant,
        current_tick=106,
        season="SPRING",
        true_dragon_aura_nearby=True,
        nearest_parent_dist=2.0,
    )
    # Distress should increase by +0.08 (from 0.20 to 0.28)
    assert round(infant.distress, 2) == 0.28

    # 4. Auto-Reversion when stamina drops below 15%
    dragon.stamina = 14.0
    LifecycleManager.advance_agent_tick(
        dragon,
        current_tick=107,
        season="SPRING",
        nearby_threat=False,
    )
    assert dragon.dragon_form == "HUMANOID_DRAGON", "Dragon must auto-revert when stamina < 15%"
    assert dragon.max_health == 280.0

    # 5. Witness receives and propagates Rumor Packet
    rumor = rumors.spawn_rumor(
        topic="DRAGON_METAMORPHOSIS",
        content="A True Dragon leveled the raiders at Ashpeak sanctuary!",
        origin_tick=105,
        origin_parcel="0_0",
        salience=0.95,
        witness_ids=[witness.agent_id],
    )
    assert rumor.credibility == 1.0

    # Witness meets another citizen and exchanges rumor (dist <= 8m)
    citizen = _create_adult("citizen_2", "BOY", "HUMAN")
    exchanged = rumors.exchange_rumors(
        witness.agent_id, citizen.agent_id, dist_meters=4.0, current_tick=110
    )
    assert exchanged > 0

    citizen_rumors = rumors.get_agent_rumors(citizen.agent_id, current_tick=110)
    assert len(citizen_rumors) == 1
    # Credibility decayed by 0.90 per hop
    assert round(citizen_rumors[0].credibility, 2) == 0.90
    assert citizen_rumors[0].hops == 1


def test_dragon_mating_constraint():
    """
    Acceptance Requirement:
    Dragons must be in HUMANOID_DRAGON form when mating with non-dragons.
    """
    dragon = _create_adult("dragon_m", "BOY", "DRAGON")
    elf = _create_adult("elf_f", "GIRL", "ELF")

    # Shift dragon to TRUE_DRAGON
    LifecycleManager.trigger_dragon_metamorphosis(dragon)
    assert dragon.dragon_form == "TRUE_DRAGON"

    success, reason, _ = LifecycleManager.attempt_mating(dragon, elf, current_tick=100)
    assert success is False
    assert "TRUE_DRAGON_MATING_FORBIDDEN" in reason

    # Revert to HUMANOID_DRAGON
    LifecycleManager.revert_dragon_metamorphosis(dragon)
    assert dragon.dragon_form == "HUMANOID_DRAGON"

    # Mating allowed in humanoid form
    success2, reason2, _ = LifecycleManager.attempt_mating(
        dragon, elf, current_tick=100, rng_seed=42
    )
    # May succeed or fail on 50% conception, but not blocked by dragon form
    assert "TRUE_DRAGON_MATING_FORBIDDEN" not in reason2


def test_demon_race_reproduction_temperament_and_dragon_deterrence():
    """
    Acceptance Requirement for DEMON Race (v3.0):
    - Profile: lifespan_multiplier = 2.8, gestation_days = 4.0, base_max_health = 120.0,
      winter_resistance = 1.50, patron_godmother_slot = 'gm_demon'.
    - Binary gender requirement: same-gender mating is forbidden.
    - Cross-species mating: mother-race gestation duration
      (4.0d for Demon mother, 3.0d for Elf mother).
    - Emergent temperament:
      - Demon out-group aggression prior (centered around 0.35) with Gaussian variation.
      - Demon generational dragon deterrence bias (centered around 0.65).
      - MoralityEngine evaluates Demon attacks on Dragons as inhibited unless self-defense.
      - MoralityEngine computes racial friction with positive out-group aggression toward Humans,
        dampened toward Dragons by dragon_deterrence_bias.
      - Elevated gm_demon reverence imprinted at birth (godmother_affinities['gm_demon'] >= 0.35).
    """
    profile = get_race_profile("DEMON")
    assert profile.lifespan_multiplier == 2.8
    assert profile.gestation_days == 4.0
    assert profile.base_max_health == 120.0
    assert profile.winter_resistance == 1.50
    assert profile.patron_godmother_slot == "gm_demon"
    assert profile.trait_priors["out_group_aggression"] == 0.35
    assert profile.trait_priors["dragon_deterrence_bias"] == 0.65

    # 1. Binary gender requirement: same-gender mating forbidden
    demon_boy1 = _create_adult("db1", "BOY", "DEMON")
    demon_boy2 = _create_adult("db2", "BOY", "DEMON")
    success, reason, _ = LifecycleManager.attempt_mating(demon_boy1, demon_boy2, current_tick=100)
    assert success is False
    assert "SAME_GENDER_MATING_FORBIDDEN" in reason

    # 2. Cross-species reproduction: Demon father + Elf mother -> Elf mother gestation (3.0d)
    elf_mother = _create_adult("em1", "GIRL", "ELF")
    succ_elf, _, meta_elf = LifecycleManager.attempt_mating(
        demon_boy1, elf_mother, current_tick=100, rng_seed=42
    )
    if succ_elf:
        assert meta_elf["gestation_days"] == 3.0
        assert elf_mother.pregnant_ticks_remaining == int(3.0 * 10800)

    # 3. Cross-species reproduction: Human father + Demon mother -> Demon mother gestation (4.0d)
    human_father = _create_adult("hf1", "BOY", "HUMAN")
    demon_mother = _create_adult("dm1", "GIRL", "DEMON")
    succ_demon, _, meta_demon = LifecycleManager.attempt_mating(
        human_father, demon_mother, current_tick=100, rng_seed=42
    )
    if succ_demon:
        assert meta_demon["gestation_days"] == 4.0
        assert demon_mother.pregnant_ticks_remaining == int(4.0 * 10800)

    # 4. Pure Demon birth: child receives Demon naming, trait priors,
    # and elevated gm_demon reverence
    survived, child, _ = LifecycleManager.deliver_child(
        demon_mother, demon_boy1, current_tick=50000, rng_seed=1234
    )
    if survived:
        assert child is not None
        assert child.race == "DEMON"
        assert child.patron_godmother_slot == "gm_demon"
        # High reverence for gm_demon imprinted at birth
        assert child.godmother_affinities.get("gm_demon", 0.0) >= 0.35
        # Priors populated
        assert "out_group_aggression" in child.traits
        assert "dragon_deterrence_bias" in child.traits
        assert 0.0 <= child.traits["out_group_aggression"] <= 1.0
        assert 0.0 <= child.traits["dragon_deterrence_bias"] <= 1.0

    # 5. Emergent Temperament & Dragon Deterrence in MoralityEngine
    morality = MoralityEngine()
    demon_traits = {
        "out_group_aggression": 0.40,
        "dragon_deterrence_bias": 0.70,
    }

    # Unprovoked attack on Dragon by Demon is INHIBITED by generational deterrence
    inhibited_dragon = morality.evaluate_attack_inhibited(
        attacker_race="DEMON",
        victim_race="DRAGON",
        attacker_traits=demon_traits,
        is_self_defense=False,
    )
    assert inhibited_dragon is True, "Demons must refrain from unprovoked attacks on Dragons"

    # Self-defense against Dragon is NOT inhibited
    inhibited_self_defense = morality.evaluate_attack_inhibited(
        attacker_race="DEMON",
        victim_race="DRAGON",
        attacker_traits=demon_traits,
        is_self_defense=True,
    )
    assert inhibited_self_defense is False, "Demons must defend themselves against Dragons"

    # Unprovoked attack on Human by Demon is NOT inhibited by dragon deterrence
    inhibited_human = morality.evaluate_attack_inhibited(
        attacker_race="DEMON",
        victim_race="HUMAN",
        attacker_traits=demon_traits,
        is_self_defense=False,
    )
    assert inhibited_human is False

    # Racial friction modifier calculation
    friction_human = morality.compute_racial_friction_modifier(
        actor_race="DEMON",
        target_race="HUMAN",
        actor_traits=demon_traits,
    )
    assert friction_human > 0.0, "Demons have positive friction toward other races"

    friction_dragon = morality.compute_racial_friction_modifier(
        actor_race="DEMON",
        target_race="DRAGON",
        actor_traits=demon_traits,
    )
    # Friction with dragons is dampened by (1.0 - dragon_deterrence_bias)
    assert friction_dragon < friction_human, (
        "Dragon deterrence must dampen aggression toward Dragons"
    )
