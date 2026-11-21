"""
tests/test_divine_hierarchy_patronage_and_councils.py
Phase 3A Mandatory Acceptance Tests:
- Mixed-race child stays uncommitted (patron_godmother_slot = None) under age 10;
  voluntary choice locks target; timeout auto-allocates higher affinity;
  exact tie escalates to World Goddess and logs decree.
- Mortals cannot pray directly to God; offensive rival-civilian miracle is blocked
  (covenant_rebukes += 1) and triggers Sister Council / World Goddess mediation.
- Active DIVINE_TRUCE blocks wartime WARD_DEFENDERS.
"""

from sim_core.divine.hierarchy import DivineHierarchyManager
from sim_core.divine.sister_council import SisterCouncilEngine
from sim_core.lifecycle import LifecycleManager
from sim_core.schemas import AgentRecord as AgentState
from sim_core.schemas import Vec3


def _create_child(
    agent_id: str,
    dominant_race: str,
    secondary_race: str,
    age_days: float = 1.0,
) -> AgentState:
    return AgentState(
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


def test_mixed_race_child_age10_patronage_choice_and_tie_break():
    """
    Acceptance Requirement:
    - Under age 10, child stays uncommitted (patron_godmother_slot = None).
    - Voluntary choice locks target God-Mother.
    - Timeout auto-allocates higher affinity.
    - Exact tie escalates to World Goddess.
    """
    # 1. Under biological age 10 (Human L=1.0, age 10 = 3.33 days; at 2.0 days bio age is ~6.0)
    child_young = _create_child("young_1", "HUMAN", "ELF", age_days=2.0)
    assert LifecycleManager.get_biological_age_years(child_young) < 10.0
    LifecycleManager.advance_agent_tick(child_young, current_tick=100)
    assert child_young.patron_godmother_slot is None, "Child under age 10 must remain uncommitted"

    # 2. At biological age 10 with voluntary choice
    child_choice = _create_child("choice_1", "HUMAN", "ELF", age_days=3.4)
    assert LifecycleManager.get_biological_age_years(child_choice) >= 10.0
    res = LifecycleManager.resolve_age10_patronage(child_choice, voluntary_choice="gm_elf")
    assert "VOLUNTARY_CHOICE_LOCKED" in res
    assert child_choice.patron_godmother_slot == "gm_elf"

    # 3. Timeout auto-allocation based on higher affinity
    child_auto = _create_child("auto_1", "HUMAN", "ELF", age_days=3.4)
    child_auto.godmother_affinities = {"gm_human": 0.85, "gm_elf": 0.40}
    res_auto = LifecycleManager.resolve_age10_patronage(child_auto)
    assert "AUTO_ALLOCATED_HIGHER_AFFINITY" in res_auto
    assert child_auto.patron_godmother_slot == "gm_human"

    # 4. Exact tie escalates to World Goddess
    child_tie = _create_child("tie_1", "HUMAN", "ELF", age_days=3.4)
    child_tie.godmother_affinities = {"gm_human": 0.50, "gm_elf": 0.50}
    # World Goddess decrees gm_elf for forest settlement balance
    res_tie = LifecycleManager.resolve_age10_patronage(
        child_tie, world_goddess_decision="gm_elf"
    )
    assert "WORLD_GODDESS_TIE_BREAK_DECREE" in res_tie
    assert child_tie.patron_godmother_slot == "gm_elf"


def test_non_aggression_covenant_and_mediation():
    """
    Acceptance Requirement:
    - Offensive rival-civilian miracle by a God-Mother is blocked (covenant_rebukes += 1).
    - Triggers Sister Council / World Goddess mediation and 1-day penalty freeze.
    """
    hierarchy = DivineHierarchyManager()
    council = SisterCouncilEngine(hierarchy)

    human_mother = hierarchy.get_deity("gm_human")
    assert human_mother.covenant_rebukes == 0

    # Attempt forbidden offensive miracle against rival civilians
    success, reason = hierarchy.execute_intervention(
        slot="gm_human",
        action="SOOTHE_OR_HEAL",
        current_tick=100,
        target_civilians=True,  # offensive targeting of civilians!
    )
    assert success is False
    assert "NON_AGGRESSION_COVENANT_BREACH" in reason
    assert human_mother.covenant_rebukes == 1

    # World Goddess mediation convenes
    mediation_msg = council.handle_covenant_breach(
        aggressor_slot="gm_human",
        victim_slot="gm_elf",
        day=1,
        tick=100,
    )
    assert mediation_msg.topic == "COVENANT_BREACH"
    assert "COVENANT_REBUKE_ISSUED" in mediation_msg.resolution
    # Aggressor frozen for 1 Game Day (10,800 ticks)
    assert human_mother.intervention_cooldown_until_tick == 100 + 10800


def test_divine_truce_blocks_wartime_ward_defenders():
    """
    Acceptance Requirement:
    - Two sisters agree to a 7-day DIVINE_TRUCE.
    - While active, WARD_DEFENDERS is blocked against each other.
    """
    hierarchy = DivineHierarchyManager()
    council = SisterCouncilEngine(hierarchy)

    # Establish truce between Human Mother and Dragon Mother
    accepted, msg = council.propose_truce(
        sender_slot="gm_human",
        target_slot="gm_dragon",
        day=2,
        tick=200,
    )
    assert accepted is True
    assert "DIVINE_TRUCE_ESTABLISHED" in msg.resolution

    human_mother = hierarchy.get_deity("gm_human")
    dragon_mother = hierarchy.get_deity("gm_dragon")
    assert "gm_dragon" in human_mother.active_truce_with
    assert "gm_human" in dragon_mother.active_truce_with

    # Human mother attempts WARD_DEFENDERS in war against Dragon kin
    success, reason = hierarchy.execute_intervention(
        slot="gm_human",
        action="WARD_DEFENDERS",
        current_tick=300,
        target_slot="gm_dragon",
    )
    assert success is False
    assert "DIVINE_TRUCE_ACTIVE" in reason


def test_demon_god_mother_hierarchy_and_council():
    """
    Acceptance Requirement for 5th Racial God-Mother (gm_demon) v3.0:
    - Registered as 5th Daughter in DivineHierarchyManager (patron_race='DEMON', name='Morvath').
    - Owns finite Divine Energy, personality vector, and obeys Non-Aggression Covenant.
    - Participates in 5-Sister Council dialogue and bilateral Divine Truces.
    - Mixed-race Demon-Human child resolves Age-10 patronage choice between gm_demon and gm_human:
      voluntary lock, timeout auto-allocation by affinity, and World Goddess tie-break decree.
    """
    hierarchy = DivineHierarchyManager()
    council = SisterCouncilEngine(hierarchy)

    # 1. Verification of gm_demon registration
    demon_mother = hierarchy.get_deity("gm_demon")
    assert demon_mother is not None
    assert demon_mother.patron_race == "DEMON"
    assert demon_mother.bestowed_name == "Morvath"
    assert demon_mother.divine_energy == 300.0
    assert demon_mother.personality.protective_fury == 0.80
    assert demon_mother.personality.pride == 0.75

    # 2. Bilateral Divine Truce with gm_dragon
    accepted, msg = council.propose_truce(
        sender_slot="gm_demon",
        target_slot="gm_dragon",
        day=3,
        tick=500,
    )
    assert accepted is True
    assert "DIVINE_TRUCE_ESTABLISHED" in msg.resolution

    dragon_mother = hierarchy.get_deity("gm_dragon")
    assert "gm_dragon" in demon_mother.active_truce_with
    assert "gm_demon" in dragon_mother.active_truce_with

    # Active truce blocks offensive ward against Dragon kin
    succ, reason = hierarchy.execute_intervention(
        slot="gm_demon",
        action="WARD_DEFENDERS",
        current_tick=510,
        target_slot="gm_dragon",
    )
    assert succ is False
    assert "DIVINE_TRUCE_ACTIVE" in reason

    # 3. Mixed-race DEMON / HUMAN child Age-10 patronage
    # Under age 10: uncommitted
    child_young = _create_child("demon_hybrid_young", "DEMON", "HUMAN", age_days=2.0)
    assert LifecycleManager.get_biological_age_years(child_young) < 10.0
    LifecycleManager.advance_agent_tick(child_young, current_tick=100)
    assert child_young.patron_godmother_slot is None

    # Age 10 voluntary choice: locks gm_demon
    # (For Demon dominant L=2.8, age 10 = 3.33 * 2.8 = 9.32 days; 10.0 days bio age is > 10.0)
    child_vol = _create_child("demon_hybrid_vol", "DEMON", "HUMAN", age_days=10.0)
    assert LifecycleManager.get_biological_age_years(child_vol) >= 10.0
    res_vol = LifecycleManager.resolve_age10_patronage(child_vol, voluntary_choice="gm_demon")
    assert "VOLUNTARY_CHOICE_LOCKED" in res_vol
    assert child_vol.patron_godmother_slot == "gm_demon"

    # Age 10 auto-allocation: chooses gm_demon when affinity is higher
    child_auto = _create_child("demon_hybrid_auto", "DEMON", "HUMAN", age_days=10.0)
    child_auto.godmother_affinities = {"gm_demon": 0.80, "gm_human": 0.30}
    res_auto = LifecycleManager.resolve_age10_patronage(child_auto)
    assert "AUTO_ALLOCATED_HIGHER_AFFINITY" in res_auto
    assert child_auto.patron_godmother_slot == "gm_demon"

    # Age 10 exact tie escalates to World Goddess decree
    child_tie = _create_child("demon_hybrid_tie", "DEMON", "HUMAN", age_days=10.0)
    child_tie.godmother_affinities = {"gm_demon": 0.50, "gm_human": 0.50}
    res_tie = LifecycleManager.resolve_age10_patronage(
        child_tie, world_goddess_decision="gm_demon"
    )
    assert "WORLD_GODDESS_TIE_BREAK_DECREE" in res_tie
    assert child_tie.patron_godmother_slot == "gm_demon"

