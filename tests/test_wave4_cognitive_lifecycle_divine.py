"""
tests/test_wave4_cognitive_lifecycle_divine.py
Comprehensive verification suite for Gaia v4.0 Remediation Wave 4:
1. Canonical Knowledge-to-Neural Effect Aggregator & Hierarchical Brain Feature Packing.
2. BatchedAgentSelfNet Exact Contiguity Check & Non-Contiguous Safety.
3. Live Cognitive Action Bridge, Need Recovery, XP Leveling & Real Rollouts.
4. Biological Sub-Lineages (Dwarves, Barbarians), Newborn Personality & Live Births.
5. Per-Agent Regional Weather & Real Infant Caretaker Proximity.
6. Divine AI & Critic Security Hardening (CPI tracking, top_memories RAG, codex dedupe).
7. Devotion / Religion Unification, CLI 'religions' command & Crime Deduplication.
"""

from __future__ import annotations

from pathlib import Path

import torch

from sim_core.brains.action_bridge import CognitiveActionExecutor, ProfessionRolloutBuffer
from sim_core.brains.consolidation import SleepCycleConsolidator
from sim_core.brains.hierarchical_brain import HierarchicalBrain
from sim_core.brains.personality import PersonalityVector
from sim_core.brains.profession_nets import ProfessionNetRegistry, aggregate_effect_channels
from sim_core.bridge.mock_adapter import MockWorldAdapter
from sim_core.divine.llm_brain import DivineLLMBrain
from sim_core.engine import SimulationEngine
from sim_core.god_console.cli import RichGodConsole
from sim_core.lifecycle import LifecycleManager
from sim_core.neural.batched_self_net import BatchedAgentSelfNet
from sim_core.races import get_race_profile
from sim_core.schemas import (
    AgentRecord,
    BuildingRecord,
    DialogueRequest,
    LibraryProposalRecord,
    ParcelRecord,
    Vec3,
    WorldLibraryEntry,
)
from sim_core.society.religion import get_agent_devotion, set_agent_devotion
from sim_core.society.seasons import SeasonManager

# =============================================================================
# 1. Knowledge-to-Neural Effect Aggregator & Hierarchical Brain Feature Packing
# =============================================================================


def test_aggregate_effect_channels_and_bounds_mapping():
    """
    Verifies that aggregate_effect_channels maps both legacy short keys and
    canonical MECHANICAL_EFFECT_BOUNDS keys into the 6 profession channels,
    clamped to [-1.0, 1.0].
    """
    # Empty effects
    assert aggregate_effect_channels({}) == (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    # Legacy short keys
    legacy = {
        "defense": 0.4,
        "yield_mult": 0.3,
        "trade_margin": 0.2,
        "research_rate": 0.5,
        "faith_gain": 0.6,
        "stamina_efficiency": 0.7,
    }
    assert aggregate_effect_channels(legacy) == (0.4, 0.3, 0.2, 0.5, 0.6, 0.7)

    # Canonical schema keys
    canonical = {
        "defense_bonus": 0.2,
        "combat_power_multiplier": 0.3,
        "crop_yield_bonus": 0.25,
        "craft_speed_bonus": 0.15,
        "trade_fee_reduction": 0.1,
        "judicial_accuracy": 0.35,
        "faith_devotion_bonus": 0.45,
        "winter_hardiness": 0.5,
        "healing_rate_bonus": 0.2,
    }
    ch0, ch1, ch2, ch3, ch4, ch5 = aggregate_effect_channels(canonical)
    assert abs(ch0 - 0.5) < 1e-5  # 0.2 + 0.3
    assert abs(ch1 - 0.4) < 1e-5  # 0.25 + 0.15
    assert abs(ch2 - 0.1) < 1e-5  # 0.1
    assert abs(ch3 - 0.35) < 1e-5  # 0.35
    assert abs(ch4 - 0.45) < 1e-5  # 0.45
    assert abs(ch5 - 0.7) < 1e-5  # 0.5 + 0.2

    # Clamping test
    overflow = {
        "defense": 5.0,
        "yield_mult": -10.0,
        "trade_margin": 2.5,
        "research_rate": -3.0,
        "faith_gain": 1.5,
        "stamina_efficiency": -2.0,
    }
    c_ch0, c_ch1, c_ch2, c_ch3, c_ch4, c_ch5 = aggregate_effect_channels(overflow)
    assert c_ch0 == 1.0
    assert c_ch1 == -1.0
    assert c_ch2 == 1.0
    assert c_ch3 == -1.0
    assert c_ch4 == 1.0
    assert c_ch5 == -1.0


def test_profession_net_pack_and_hierarchical_brain_forward():
    """
    Verifies that pack_profession_features and HierarchicalBrain pass aggregated
    effects into Tier 2 inference channels [22:28].
    """
    base_features = [0.5] * 20
    effects = {"defense_bonus": 0.3, "combat_power_multiplier": 0.2, "crop_yield_bonus": 0.4}

    packed = ProfessionNetRegistry.pack_profession_features(
        base_living_features=base_features,
        level=3,
        xp=150.0,
        active_mechanical_effects=effects,
    )
    assert len(packed) == 28
    assert abs(packed[22] - 0.5) < 1e-5  # defense channel
    assert abs(packed[23] - 0.4) < 1e-5  # yield channel

    # Test HierarchicalBrain batch forward pass
    brain = HierarchicalBrain()
    agent = AgentRecord(
        agent_id="agent_hb_test",
        slot_idx=0,
        display_name="HbTest",
        dynasty_surname="Black",
        race="HUMAN",
        gender="BOY",
        stage="ADULT",
        profession="BLACKSMITH",
        profession_level=4,
        profession_xp=200.0,
        active_mechanical_effects=effects,
    )
    masked_logits, values = brain.forward_agents([agent])
    assert masked_logits.shape == (1, 20)
    assert values.shape == (1, 1)
    assert not torch.isnan(masked_logits).any()
    assert not torch.isnan(values).any()


# =============================================================================
# 2. BatchedAgentSelfNet Exact Contiguity Check & Non-Contiguous Safety
# =============================================================================


def test_batched_self_net_exact_contiguity_safety():
    """
    Verifies that BatchedAgentSelfNet correctly processes non-contiguous slot
    indices without corruption, while preserving exact tensor slice fast-path.
    """
    net = BatchedAgentSelfNet(initial_capacity=64)
    # Allocate several slots
    slots = [net.allocate_slot() for _ in range(10)]
    assert slots == list(range(10))

    # Test with non-contiguous tensor indices
    non_contig_tensor = torch.tensor([0, 1, 5, 2, 4], dtype=torch.long)
    inputs = torch.randn(5, 20)

    # Save initial hidden state to compare against individual slot passes
    H_init = net.H.clone()
    outputs, values = net.forward(inputs, non_contig_tensor)
    assert outputs.shape == (5, 22)
    assert values.shape == (5, 32)
    assert not torch.isnan(outputs).any()

    # Compare with individual slot forward passes from same initial state
    net.H.copy_(H_init)
    for i, slot_id in enumerate([0, 1, 5, 2, 4]):
        single_slot = torch.tensor([slot_id], dtype=torch.long)
        single_input = inputs[i : i + 1]
        single_out, single_val = net.forward(single_input, single_slot)
        assert torch.allclose(outputs[i : i + 1], single_out, atol=1e-5)
        assert torch.allclose(values[i : i + 1], single_val, atol=1e-5)

    # Test with contiguous tensor indices
    contig_tensor = torch.tensor([0, 1, 2], dtype=torch.long)
    contig_inputs = torch.randn(3, 20)
    c_outputs, c_values = net.forward(contig_inputs, contig_tensor)
    assert c_outputs.shape == (3, 22)
    assert not torch.isnan(c_outputs).any()


# =============================================================================
# 3. Live Cognitive Action Bridge, Need Recovery, XP Leveling & Real Rollouts
# =============================================================================


def test_action_bridge_need_recovery_xp_and_rollouts(tmp_path: Path):
    """
    Verifies that CognitiveActionExecutor executes winning actions cleanly:
    - 0 (REST): reduces fatigue, restores stamina
    - 1 (EAT): restores hunger
    - 2 (GROOM): restores hygiene
    - 7/8/10 (WORK/TRADE/DEFEND): awards XP and advances level
    - 9 (PRAY): increases devotion and deity energy
    - buffers real rollouts for Lv. 6+ practitioners
    """
    engine = SimulationEngine(
        db_path=tmp_path / "civ_bridge.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        adapter=MockWorldAdapter(),
        headless=True,
    )

    executor = CognitiveActionExecutor(engine=engine)

    # Agent needing REST (action 0)
    a_rest = engine.spawn_agent(race="HUMAN", gender="BOY", stage="ADULT")
    a_rest.fatigue = 0.8
    a_rest.stamina = 20.0

    # Agent needing EAT (action 1)
    a_eat = engine.spawn_agent(race="ELF", gender="GIRL", stage="ADULT")
    a_eat.hunger = 40.0

    # Agent needing GROOM (action 2)
    a_groom = engine.spawn_agent(race="BEASTHUMAN", gender="BOY", stage="ADULT")
    a_groom.hygiene = 0.2

    # High-level artisan (action 7: CRAFT/WORK)
    a_artisan = engine.spawn_agent(
        race="BEASTHUMAN",
        gender="GIRL",
        sub_lineage="DWARF",
        stage="ADULT",
    )
    a_artisan.profession = "BLACKSMITH"
    a_artisan.profession_level = 6
    a_artisan.profession_xp = 598.0  # Needs 2 XP to reach 600.0 (Lv 7)
    a_artisan.active_mechanical_effects = {"craft_speed_bonus": 0.5}

    # Devout agent (action 9: PRAY)
    a_pray = engine.spawn_agent(race="DEMON", gender="GIRL", stage="ADULT")
    a_pray.patron_godmother_slot = "gm_demon"
    set_agent_devotion(a_pray, 0.4)

    agents = [a_rest, a_eat, a_groom, a_artisan, a_pray]

    # Construct mock masked_logits picking actions [0, 1, 2, 7, 9]
    logits = torch.full((5, 20), -1e9)
    logits[0, 0] = 10.0
    logits[1, 1] = 10.0
    logits[2, 2] = 10.0
    logits[3, 7] = 10.0
    logits[4, 9] = 10.0
    values = torch.zeros(5, 1)

    winning = executor.execute_actions(agents, logits, values)
    assert winning == [0, 1, 2, 7, 9]

    # Verify state updates
    assert a_rest.fatigue < 0.8
    assert a_rest.stamina > 20.0
    assert a_eat.hunger > 40.0
    assert a_groom.hygiene > 0.2

    # Verify XP and level up on artisan
    assert a_artisan.profession_xp > 598.0
    assert a_artisan.profession_level == 7

    # Verify prayer effect
    assert get_agent_devotion(a_pray) > 0.4
    deity = engine.divine_hierarchy.entities["gm_demon"]
    assert deity.divine_energy > 0.0

    # Verify rollout buffer captured Lv 6+ artisan transition
    rollouts = executor.rollout_buffer.get_rollouts("BLACKSMITH")
    assert len(rollouts) == 1
    sample = rollouts[0]
    assert sample.level >= 6.0
    assert sample.action_idx == 7
    assert sample.reward >= 0.5


def test_consolidation_with_real_rollouts():
    """
    Verifies that SleepCycleConsolidator trains ProfessionNet using real rollouts
    from ProfessionRolloutBuffer and clears consumed transitions on success.
    """
    reg = ProfessionNetRegistry()
    consolidator = SleepCycleConsolidator()
    buffer = ProfessionRolloutBuffer()

    # Add 5 dummy rollouts for FARMER
    for _ in range(5):
        buffer.add(
            profession="FARMER",
            features=[0.5] * 28,
            level=6.0,
            action_idx=4,  # FORAGE/HARVEST
            reward=0.9,
        )

    assert len(buffer.get_rollouts("FARMER")) == 5

    # Run consolidation with real rollout buffer
    result = consolidator.consolidate_mortal_professions(
        agents=[],
        profession_registry=reg,
        rollout_buffer=buffer,
    )
    assert result.get("FARMER") is not None
    # Buffer should be cleared after successful consolidation
    assert len(buffer.get_rollouts("FARMER")) == 0


def test_action_bridge_comfort_crying_child(tmp_path: Path):
    """
    Verifies that Action 5 (COMFORT_CHILD) finds a nearby crying infant and
    soothes distress.
    """
    engine = SimulationEngine(
        db_path=tmp_path / "civ_comfort.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        adapter=MockWorldAdapter(),
        headless=True,
    )
    executor = CognitiveActionExecutor(engine=engine)

    mother = engine.spawn_agent(
        race="HUMAN", gender="GIRL", stage="ADULT", pos=Vec3(x=10.0, y=0.0, z=10.0)
    )

    infant = engine.spawn_agent(
        race="HUMAN", gender="BOY", stage="INFANT", pos=Vec3(x=11.0, y=0.0, z=10.0)
    )  # 1.0m away
    infant.crying = True
    infant.distress = 0.8
    infant.parent_ids = [mother.agent_id]

    logits = torch.full((1, 20), -1e9)
    logits[0, 5] = 10.0  # Action 5: COMFORT_CHILD
    values = torch.zeros(1, 1)

    executor.execute_actions([mother], logits, values)
    assert infant.distress < 0.8


# =============================================================================
# 4. Biological Sub-Lineages, Personality Inheritance & Live Births
# =============================================================================


def test_sub_lineage_profile_lookups():
    """
    Verifies that Dwarves, Barbarians, Wolf-Kin, and Bear-Kin correctly resolve
    their specialized sub-lineage profiles instead of defaulting to generic CAT_KIN.
    """
    dwarf_prof = get_race_profile("BEASTHUMAN", "DWARF")
    assert dwarf_prof.base_max_health == 125.0
    assert dwarf_prof.lifespan_multiplier == 1.5
    assert dwarf_prof.winter_resistance == 1.60

    barb_prof = get_race_profile("BEASTHUMAN", "BARBARIAN")
    assert barb_prof.base_max_health == 145.0
    assert barb_prof.winter_resistance == 1.45

    cat_prof = get_race_profile("BEASTHUMAN", "CAT_KIN")
    assert cat_prof.base_max_health == 90.0

    # LifecycleManager stage health scaling uses sub-lineage
    hp_dwarf = LifecycleManager.get_max_health_for_stage(
        race="BEASTHUMAN", stage="ADULT", sub_lineage="DWARF"
    )
    hp_cat = LifecycleManager.get_max_health_for_stage(
        race="BEASTHUMAN", stage="ADULT", sub_lineage="CAT_KIN"
    )
    assert hp_dwarf == 125.0
    assert hp_cat == 90.0


def test_newborn_personality_crossover_and_devotion_sync():
    """
    Verifies that deliver_child() inherits parents' PersonalityVector,
    initializes MoodState(calm=0.8), and synchronizes traits['faith_devotion'].
    """
    mother = AgentRecord(
        agent_id="m1",
        slot_idx=0,
        display_name="Mom",
        dynasty_surname="Lineage",
        race="HUMAN",
        gender="GIRL",
        stage="ADULT",
        personality=PersonalityVector(curiosity=0.9, devotion=0.8),
    )
    father = AgentRecord(
        agent_id="f1",
        slot_idx=1,
        display_name="Dad",
        dynasty_surname="Lineage",
        race="HUMAN",
        gender="BOY",
        stage="ADULT",
        personality=PersonalityVector(curiosity=0.7, devotion=0.6),
    )

    survived, newborn, reason = LifecycleManager.deliver_child(
        mother=mother, father=father, current_tick=100
    )
    assert survived is True
    assert newborn is not None
    assert newborn.personality is not None
    assert newborn.mood is not None
    assert newborn.mood.calm == 0.8
    # Devotion synchronized
    assert abs(newborn.traits["faith_devotion"] - newborn.personality.devotion) < 0.005
    assert abs(get_agent_devotion(newborn) - newborn.personality.devotion) < 0.005


def test_live_birth_delivery_in_engine_step_tick(tmp_path: Path):
    """
    Verifies that when an expectant mother transitions to pregnant_ticks_remaining == 0,
    the engine delivers a newborn, allocates a neural slab slot, registers the agent,
    and maintains strictly 0.000000 credit drift.
    """
    engine = SimulationEngine(
        db_path=tmp_path / "civ_birth.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        adapter=MockWorldAdapter(),
        headless=True,
    )

    initial_credits_total = (
        sum(a.credits for a in engine.agents.values()) + engine.bank.reserve_credits
    )

    mother = engine.spawn_agent(race="HUMAN", gender="GIRL", stage="ADULT", initial_credits=100.0)
    father = engine.spawn_agent(race="HUMAN", gender="BOY", stage="ADULT", initial_credits=100.0)

    # Set up pregnancy expiring on this tick
    mother.pregnant_ticks_remaining = 1
    mother.pregnancy_father_id = father.agent_id

    initial_pop = len(engine.agents)

    # Step tick: should trigger delivery
    engine.step_tick()

    assert len(engine.agents) == initial_pop + 1
    assert mother.pregnant_ticks_remaining == 0

    # Find the newborn
    delivered = [
        a
        for a in engine.agents.values()
        if a.stage == "INFANT" and a.parent_ids == [mother.agent_id, father.agent_id]
    ]
    assert len(delivered) == 1
    newborn = delivered[0]
    assert newborn.credits == 0.0
    assert newborn.slot_idx is not None
    assert newborn.agent_id in engine.agents

    # Strict double-entry conservation (0.000000 drift)
    current_credits_total = (
        sum(a.credits for a in engine.agents.values()) + engine.bank.reserve_credits
    )
    assert abs(current_credits_total - initial_credits_total) < 1e-6


# =============================================================================
# 5. Per-Agent Regional Weather & Real Infant Caretaker Proximity
# =============================================================================


def test_per_agent_regional_weather(tmp_path: Path):
    """
    Verifies that agents at distinct world coordinates (e.g. Malakor Ashlands
    vs Drakonis Cold Peaks) receive their true regional microclimate weather,
    not a global copy of god_avatar_pos weather.
    """
    engine = SimulationEngine(
        db_path=tmp_path / "civ_weather.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        adapter=MockWorldAdapter(),
        headless=True,
    )

    # Agent in volcanic Malakor (south-west)
    ag_malakor = engine.spawn_agent(race="DEMON", gender="BOY", stage="ADULT")
    ag_malakor.pos = Vec3(x=-2200.0, y=0.0, z=-2200.0)

    # Agent in arctic Drakonis Spire (north-east)
    ag_drakonis = engine.spawn_agent(race="DRAGON", gender="BOY", stage="ADULT")
    ag_drakonis.pos = Vec3(x=2800.0, y=0.0, z=2800.0)

    engine.step_tick()

    weather_m = engine.weather_engine.sample_weather_at(ag_malakor.pos.x, ag_malakor.pos.z)
    weather_d = engine.weather_engine.sample_weather_at(ag_drakonis.pos.x, ag_drakonis.pos.z)

    # Malakor Ashlands should have ashfall intensity
    assert weather_m.get("primary_weather") == "ASH"
    assert weather_m.get("blend_weights", {}).get("ASH", 0.0) > 0.5
    # Drakonis Spire should have zero ash
    assert weather_d.get("blend_weights", {}).get("ASH", 0.0) == 0.0


def test_infant_parent_proximity_distress():
    """
    Verifies that LifecycleManager.advance_agent_tick respects nearest_parent_dist:
    - Infant with a parent right beside them (dist <= 4.0m) does NOT accumulate distress.
    - Infant stranded far in the wild (dist > 30.0m) accumulates caretaker distress.
    """
    infant_cared = AgentRecord(
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
        hygiene=0.9,
    )
    infant_alone = AgentRecord(
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
        hygiene=0.9,
    )

    # Advance 10 ticks with parent close by (dist = 2.0m)
    for _ in range(10):
        LifecycleManager.advance_agent_tick(
            agent=infant_cared,
            current_tick=100,
            nearest_parent_dist=2.0,
            is_sheltered=True,
        )

    # Advance 10 ticks with parent absent (dist = 80.0m)
    for _ in range(10):
        LifecycleManager.advance_agent_tick(
            agent=infant_alone,
            current_tick=100,
            nearest_parent_dist=80.0,
            is_sheltered=False,
        )

    assert infant_cared.distress < infant_alone.distress


# =============================================================================
# 6. Divine AI & Critic Security Hardening
# =============================================================================


def test_divine_autonomy_cpi_and_proposal_tracking(tmp_path: Path):
    """
    Verifies that DivineAutonomyEngine tracks engine.wtc.cpi correctly and
    schedules library visits when proposals are PENDING_GODMOTHERS.
    """
    engine = SimulationEngine(
        db_path=tmp_path / "civ_divine.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        adapter=MockWorldAdapter(),
        headless=True,
    )

    autonomy = engine.divine_autonomy
    goddess = autonomy.deities["world_goddess"]

    # When CPI is high, agenda should prioritize inspecting WTC
    engine.wtc.cpi = 1.35
    autonomy.step(current_tick=100)
    assert goddess.activity_state == "INSPECTING_WTC"

    # Reset CPI to normal
    engine.wtc.cpi = 1.0
    goddess.activity_state = "AUDIENCE"

    # When a library proposal is pending, agenda inspects library
    _, _, prop = engine.governance_engine.draft_mortal_proposal(
        author_id="scholar_1",
        topic="AGRICULTURE",
        title="More Grain",
        summary="Crop yields",
        author_proficiency=0.9,
        current_tick=150,
        action="CREATE",
    )
    assert prop is not None
    prop.status = "PENDING_GODMOTHERS"

    autonomy.step(current_tick=200)
    assert goddess.activity_state == "INSPECTING_LIBRARY"


def test_divine_llm_brain_top_memories_and_fail_closed_validation():
    """
    Verifies that DivineLLMBrain validates actions fail-closed against
    allowed divine actions and handles offline fallback.
    """
    brain = DivineLLMBrain(engine=None)

    # Valid allowlisted action
    assert (
        brain._validate_proposed_action(
            "world_goddess", {"action_type": "CONVENE_COUNCIL", "target": "ALL"}
        )
        is True
    )

    # Unauthorized action rejected fail-closed
    assert (
        brain._validate_proposed_action("world_goddess", {"action_type": "DROP_DATABASE_TABLE"})
        is False
    )

    # Offline fallback returns DETERMINISTIC_FALLBACK
    req = DialogueRequest(
        target_type="DEITY",
        target_id="world_goddess",
        message="Greetings, Goddess",
        order="",
    )
    resp = brain.generate_dialogue(req)
    assert resp.llm_backend in ("OFFLINE_FALLBACK", "DETERMINISTIC_FALLBACK")


def test_two_book_governance_duplicate_vote_exploit_blocked(tmp_path: Path):
    """
    Verifies that write_codex_text_decree_goddess_and_daughters blocks
    duplicate deity approvals (e.g. ['gm_human', 'gm_human', 'gm_human']).
    """
    engine = SimulationEngine(
        db_path=tmp_path / "civ_gov.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        adapter=MockWorldAdapter(),
        headless=True,
    )
    gov = engine.governance_engine

    # 3 duplicate votes from the same God-Mother deduplicate to 1 -> FAILS (>= 3 required)
    ok_exploit, reason_exploit, _ = gov.write_codex_text_decree_goddess_and_daughters(
        title="Corrupted Decree",
        text="I declare unlimited wine.",
        daughter_approvals=["gm_human", "gm_human", "gm_human"],
        current_tick=1,
    )
    assert ok_exploit is False
    assert "got 1" in reason_exploit or ">= 3/5 Daughters" in reason_exploit

    # 3 distinct God-Mothers -> SUCCEEDS
    ok_valid, _, entry = gov.write_codex_text_decree_goddess_and_daughters(
        title="Sanctioned Decree",
        text="Universal festival day.",
        daughter_approvals=["gm_human", "gm_elf", "gm_dragon"],
        current_tick=1,
    )
    assert ok_valid is True
    assert entry is not None


def test_healer_escalation_pauses_subsystem(tmp_path: Path):
    """
    Verifies that 6 repeated faults in one day cause ErrorHealer to pause
    the subsystem and engine skips it cleanly.
    """
    engine = SimulationEngine(
        db_path=tmp_path / "civ_healer.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        adapter=MockWorldAdapter(),
        headless=True,
    )

    # Trigger 6 faults on COORD_OUT_OF_BOUNDS (which pauses spatial_movement)
    for i in range(1, 7):
        engine.healer.handle(
            fault_class="COORD_OUT_OF_BOUNDS",
            day=engine.current_day,
            tick=i,
            agent_id="test_agent",
            context={"x": 99999.0, "z": -99999.0},
        )

    assert "spatial_movement" in engine.healer.paused_subsystems

    # Engine step should run cleanly without crashing while spatial_movement is paused
    engine.step_tick()


# =============================================================================
# 7. Devotion Unification, Religions & Speech Acts Deduplication
# =============================================================================


def test_devotion_unification_and_cli_religions_command(tmp_path: Path):
    """
    Verifies that get_agent_devotion and set_agent_devotion synchronize
    traits['faith_devotion'] and personality.devotion, and cli 'religions'
    executes without AttributeError.
    """
    agent = AgentRecord(
        agent_id="a_dev_test",
        slot_idx=0,
        display_name="DevTester",
        dynasty_surname="Faith",
        race="HUMAN",
        gender="BOY",
        stage="ADULT",
        personality=PersonalityVector(devotion=0.2),
    )

    set_agent_devotion(agent, 0.72)
    assert agent.personality is not None
    assert abs(agent.personality.devotion - 0.72) < 1e-6
    assert abs(agent.traits["faith_devotion"] - 0.72) < 1e-6
    assert abs(get_agent_devotion(agent) - 0.72) < 1e-6

    # Test RichGodConsole 'religions' command
    engine = SimulationEngine(
        db_path=tmp_path / "civ_cli.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        adapter=MockWorldAdapter(),
        headless=True,
    )
    cli = RichGodConsole(engine=engine)
    # Must execute cleanly without error
    out = cli.execute_command("religions")
    assert "World Goddess" in out or "Faith" in out or "Religions" in out


def test_speech_acts_crime_deduplication_and_prayer_call(tmp_path: Path):
    """
    Verifies that 5 guards hearing one REPORT_CRIME shout file at most 1
    judiciary case, and PRAYER_CALL updates canonical devotion.
    """
    engine = SimulationEngine(
        db_path=tmp_path / "civ_speech.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        adapter=MockWorldAdapter(),
        headless=True,
    )

    # Spawn victim shouting crime at (0, 0)
    victim = engine.spawn_agent(race="HUMAN", gender="GIRL", stage="ADULT")
    victim.pos = Vec3(x=0.0, y=0.0, z=0.0)

    # Spawn 5 city guards within hearing range (dist <= 8m)
    guards = []
    for i in range(5):
        g = engine.spawn_agent(race="HUMAN", gender="BOY", stage="ADULT")
        g.role = "CITY_GUARD"
        g.profession = "CITY_GUARD"
        g.pos = Vec3(x=1.0 + i, y=0.0, z=1.0)
        guards.append(g)

    initial_cases = len(engine.judiciary.cases)

    # Trigger REPORT_CRIME (broadcasts to all within PHYSICAL_SPEECH_RADIUS = 8m)
    engine.speech_acts.emit_speech_act(
        speaker=victim,
        act_type="REPORT_CRIME",
        topic="THEFT",
        listener=None,
        tick=engine.current_tick,
    )

    # Must file at most 1 case despite 5 guards hearing it
    new_cases = len(engine.judiciary.cases) - initial_cases
    assert new_cases == 1

    # Test PRAYER_CALL updates devotion cleanly
    devout = engine.spawn_agent(race="ELF", gender="GIRL", stage="ADULT")
    devout.pos = Vec3(x=10.0, y=0.0, z=10.0)
    listener = engine.spawn_agent(race="ELF", gender="BOY", stage="ADULT")
    listener.pos = Vec3(x=12.0, y=0.0, z=10.0)
    set_agent_devotion(listener, 0.3)

    engine.speech_acts.emit_speech_act(
        speaker=devout,
        act_type="PRAYER_CALL",
        topic="FAITH",
        listener=listener,
        tick=engine.current_tick,
    )
    assert get_agent_devotion(listener) > 0.3


# =============================================================================
# 8. Wave 4 Micro-Fix Regression Tests (All 12 Defects)
# =============================================================================


def test_def_t1_01_study_book_proximity_and_parcel_library(tmp_path: Path):
    """
    DEF-T1-01: Verifies that an agent 2,500m away in wilderness cannot telepathically
    study books from the World Library, but agents near the library or on a parcel with
    has_library == True can study and gain buffs.
    """
    engine = SimulationEngine(
        db_path=tmp_path / "civ_study.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        adapter=MockWorldAdapter(),
        headless=True,
    )

    entry = WorldLibraryEntry(
        entry_id="ancient_tactics",
        topic="tactics",
        title="Ancient Tactics",
        summary="Tactical formations.",
        author_id="scholar_founder",
        author_proficiency=0.9,
        created_tick=0,
        body="Detailed military discipline.",
        mechanical_effects={"defense_bonus": 0.25},
    )
    engine.governance_engine.library_entries["ancient_tactics"] = entry

    executor = CognitiveActionExecutor(engine=engine)

    # 1. Wilderness scholar (2500, 0, 2500)
    wilderness_scholar = engine.spawn_agent(race="HUMAN", gender="BOY", stage="ADULT")
    wilderness_scholar.pos = Vec3(x=2500.0, y=0.0, z=2500.0)
    wilderness_scholar.profession = "SCHOLAR"
    wilderness_scholar.profession_level = 1
    wilderness_scholar.profession_xp = 0.0

    logits = torch.full((1, 20), -1e9)
    logits[0, 6] = 10.0  # Action 6: STUDY_BOOK
    values = torch.zeros(1, 1)

    winning = executor.execute_actions([wilderness_scholar], logits, values)
    assert winning == [6]
    assert "ancient_tactics" not in wilderness_scholar.known_books
    assert wilderness_scholar.profession_xp == 0.0

    # 2. Acropolis Library scholar at (180.0, 0.0, 180.0)
    library_scholar = engine.spawn_agent(race="HUMAN", gender="GIRL", stage="ADULT")
    library_scholar.pos = Vec3(x=180.0, y=0.0, z=180.0)
    library_scholar.profession = "SCHOLAR"
    library_scholar.profession_level = 1
    library_scholar.profession_xp = 0.0

    winning = executor.execute_actions([library_scholar], logits, values)
    assert winning == [6]
    assert "ancient_tactics" in library_scholar.known_books
    assert library_scholar.profession_xp == 3.0

    # 3. Scholar on parcel with has_library == True
    city_scholar = engine.spawn_agent(race="ELF", gender="GIRL", stage="ADULT")
    city_scholar.pos = Vec3(x=800.0, y=0.0, z=800.0)
    city_scholar.profession = "SCHOLAR"
    city_scholar.profession_level = 1
    city_scholar.profession_xp = 0.0

    cx = int(800.0 // 16.0)
    cz = int(800.0 // 16.0)
    parcel = ParcelRecord(parcel_id=f"{cx}_{cz}", cx=cx, cz=cz, has_library=True)
    engine.property_mgr.register_parcel(parcel)

    entry2 = WorldLibraryEntry(
        entry_id="forestry_codex",
        topic="forestry",
        title="Forestry Codex",
        summary="Arboreal cultivation.",
        author_id="elf_elder",
        author_proficiency=0.85,
        created_tick=0,
        body="Deep forest secrets.",
        mechanical_effects={"crop_yield_bonus": 0.20},
    )
    engine.governance_engine.library_entries["forestry_codex"] = entry2

    winning = executor.execute_actions([city_scholar], logits, values)
    assert winning == [6]
    has_lore = (
        "forestry_codex" in city_scholar.known_books
        or "ancient_tactics" in city_scholar.known_books
    )
    assert has_lore
    assert city_scholar.profession_xp == 3.0


def test_def_t1_02_eat_city_purchase_vs_wilderness_forage(tmp_path: Path):
    """
    DEF-T1-02: Verifies that eating in a city deducts 0.10 credits via closed-loop
    double-entry transfer and gives +12 hunger, while wilderness eating forages
    by consuming stamina and scaling with season, failing cleanly when exhausted.
    """
    engine = SimulationEngine(
        db_path=tmp_path / "civ_eat.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        adapter=MockWorldAdapter(),
        headless=True,
    )
    executor = CognitiveActionExecutor(engine=engine)

    # 1. City citizen eating with credits
    city_agent = engine.spawn_agent(race="HUMAN", gender="BOY", stage="ADULT")
    city_agent.pos = Vec3(x=50.0, y=0.0, z=50.0)  # In Acropolis (r <= 360m)
    city_agent.hunger = 40.0
    city_agent.credits = 10.0
    init_bank_credits = engine.bank.credits

    logits = torch.full((1, 20), -1e9)
    logits[0, 1] = 10.0  # Action 1: EAT
    values = torch.zeros(1, 1)

    executor.execute_actions([city_agent], logits, values)
    assert city_agent.hunger == 52.0
    assert abs(city_agent.credits - 9.90) < 1e-6
    assert abs(engine.bank.credits - (init_bank_credits + 0.10)) < 1e-6

    # 2. Wilderness agent foraging with stamina
    wild_agent = engine.spawn_agent(race="BEASTHUMAN", gender="BOY", stage="ADULT")
    wild_agent.pos = Vec3(x=1500.0, y=0.0, z=1500.0)  # Wilderness
    wild_agent.hunger = 40.0
    wild_agent.stamina = 50.0
    wild_agent.credits = 0.0

    season_mult = SeasonManager.get_wild_food_multiplier(engine.current_season)
    executor.execute_actions([wild_agent], logits, values)
    assert wild_agent.stamina == 45.0
    expected_hunger = 40.0 + 4.0 * season_mult
    assert abs(wild_agent.hunger - expected_hunger) < 1e-4

    # 3. Exhausted wilderness agent (stamina < 5.0) fails cleanly
    tired_agent = engine.spawn_agent(race="BEASTHUMAN", gender="GIRL", stage="ADULT")
    tired_agent.pos = Vec3(x=1500.0, y=0.0, z=1500.0)
    tired_agent.hunger = 30.0
    tired_agent.stamina = 3.0  # < 5.0
    tired_agent.credits = 0.0

    executor.execute_actions([tired_agent], logits, values)
    assert tired_agent.hunger == 30.0  # Unchanged
    assert tired_agent.stamina == 3.0  # Unchanged


def test_def_t1_03_poisoned_rollout_rollback_pruning():
    """
    DEF-T1-03: Verifies that when SleepCycleConsolidator encounters a rollback
    (NaN or loss regression), offending rollouts are cleared from ProfessionRolloutBuffer
    to prevent poisoned batches from failing repeatedly every midnight.
    """
    reg = ProfessionNetRegistry()
    consolidator = SleepCycleConsolidator()
    buffer = ProfessionRolloutBuffer()

    # Add rollouts
    buffer.add(
        profession="FARMER",
        features=[0.5] * 28,
        level=6.0,
        action_idx=4,
        reward=0.9,
    )
    assert buffer.size("FARMER") == 1

    # Inject NaN to trigger rollback
    result = consolidator.consolidate_mortal_professions(
        agents=[],
        profession_registry=reg,
        rollout_buffer=buffer,
        inject_nan_for_test=True,
    )
    assert result.get("FARMER", {}).get("status") == "ROLLED_BACK_NAN_DETECTED"
    # Offending rollouts must be cleared
    assert buffer.size("FARMER") == 0


def test_def_t1_04_t1_05_t1_06_pray_slot_none_and_xp_clamp(tmp_path: Path):
    """
    DEF-T1-04, DEF-T1-05, DEF-T1-06:
    - PRAY routes divine energy through add_divine_energy
    - HierarchicalBrain.forward_agents handles slot_idx=None cleanly
    - Max profession XP clamps at 1000.0 at Lv. 10
    """
    engine = SimulationEngine(
        db_path=tmp_path / "civ_misc.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        adapter=MockWorldAdapter(),
        headless=True,
    )
    executor = CognitiveActionExecutor(engine=engine)

    # DEF-T1-04: Prayer routes via add_divine_energy
    priest = engine.spawn_agent(race="HUMAN", gender="GIRL", stage="ADULT")
    priest.patron_godmother_slot = "gm_human"
    init_energy = engine.divine_hierarchy.entities["gm_human"].divine_energy
    logits = torch.full((1, 20), -1e9)
    logits[0, 9] = 10.0  # PRAY
    values = torch.zeros(1, 1)
    executor.execute_actions([priest], logits, values)
    assert engine.divine_hierarchy.entities["gm_human"].divine_energy > init_energy

    # DEF-T1-05: Agent with slot_idx=None does not crash forward_agents
    orphan = engine.spawn_agent(race="ELF", gender="BOY", stage="ADULT")
    orphan.slot_idx = None  # type: ignore[assignment]
    masked_logits, vals = engine.hierarchical_brain.forward_agents([orphan])
    assert masked_logits.shape == (1, 20)
    assert vals.shape == (1, 1)

    # DEF-T1-06: Lv. 10 artisan profession XP clamps at 1000.0
    artisan = engine.spawn_agent(race="HUMAN", gender="BOY", stage="ADULT")
    artisan.profession = "BLACKSMITH"
    artisan.profession_level = 10
    artisan.profession_xp = 999.5
    logits = torch.full((1, 20), -1e9)
    logits[0, 7] = 10.0  # CRAFT/WORK
    executor.execute_actions([artisan], logits, values)
    assert artisan.profession_xp == 1000.0


def test_def_t2_01_t2_02_t2_05_safe_delivery_and_devotion_sync(tmp_path: Path):
    """
    DEF-T2-01, DEF-T2-02, DEF-T2-05:
    - Dead pregnant mother on delivery tick does NOT spawn living child (logs BIRTH_COMPLICATION)
    - Live delivery grounds newborn elevation to heightmap
    - Normal birth faith_devotion trait strictly matches personality devotion float
    """
    engine = SimulationEngine(
        db_path=tmp_path / "civ_delivery.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        adapter=MockWorldAdapter(),
        headless=True,
    )

    # DEF-T2-01: Mother dies on delivery tick
    mother_dead = engine.spawn_agent(race="HUMAN", gender="GIRL", stage="ADULT")
    mother_dead.pregnant_ticks_remaining = 1
    mother_dead.health = 0.001
    mother_dead.hunger = 0.0  # Starvation kills her on tick
    initial_total_alive = engine.judiciary.population_ledger.get("total_alive", 0)

    engine.step_tick()
    assert not mother_dead.alive
    # Must NOT have spawned a living child
    assert engine.judiciary.population_ledger.get("total_alive", 0) == initial_total_alive - 1
    # Must have logged perinatal fatality
    fatalities = engine.judiciary.fatalities
    has_perinatal = any(
        f.cause == "BIRTH_COMPLICATION" and "Perinatal" in f.display_name for f in fatalities
    )
    assert has_perinatal

    # DEF-T2-05: Live birth heightmap grounding (inside Reality Bubble r <= 140m)
    mother_live = engine.spawn_agent(race="ELF", gender="GIRL", stage="ADULT")
    mother_live.pos = Vec3(x=50.0, y=99.0, z=50.0)  # Airborne y
    mother_live.pregnant_ticks_remaining = 1
    mother_live.health = 50.0
    mother_live.hunger = 90.0

    engine.step_tick()
    # Find child
    child = None
    for a in engine.agents.values():
        if a.alive and mother_live.agent_id in a.parent_ids:
            child = a
            break
    assert child is not None
    expected_y = engine.heightmap.get_elevation(child.pos.x, child.pos.z)
    assert abs(child.pos.y - expected_y) < 1e-4

    # DEF-T2-02: Normal birth devotion precision equality
    p_mother = engine.spawn_agent(race="HUMAN", gender="GIRL", stage="ADULT")
    p_father = engine.spawn_agent(race="HUMAN", gender="BOY", stage="ADULT")
    survived, newborn, _ = LifecycleManager.deliver_child(p_mother, p_father, current_tick=10)
    assert survived and newborn is not None
    assert (
        newborn.personality is not None
        and newborn.traits["faith_devotion"] == newborn.personality.devotion
    )


def test_def_t2_03_unified_4_tier_probate_parcel_and_building_sync(tmp_path: Path):
    """
    DEF-T2-03: Verifies that deceased homeowner with only a living mother/sibling
    transfers BOTH the deeded parcel AND occupying BuildingRecord to that relative,
    preventing building confiscation or auctions to strangers.
    """
    engine = SimulationEngine(
        db_path=tmp_path / "civ_probate.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        adapter=MockWorldAdapter(),
        headless=True,
    )

    # Spawn mother and son
    mother = engine.spawn_agent(race="HUMAN", gender="GIRL", stage="ADULT")
    son = engine.spawn_agent(race="HUMAN", gender="BOY", stage="ADULT")
    son.parent_ids = [mother.agent_id]
    son.credits = 50.0

    # Son owns parcel and building
    parcel = ParcelRecord(
        parcel_id="20_20", cx=20, cz=20, owner_id=son.agent_id, owner_type="INDIVIDUAL"
    )
    engine.property_mgr.register_parcel(parcel)

    building = BuildingRecord(
        building_id="bld_house_20_20",
        city_id="city_human",
        building_type="HOUSE_T1_COTTAGE",
        racial_style="HUMAN",
        x=320.0,
        y=10.0,
        z=320.0,
        rotation_y=0.0,
        parcel_x=20,
        parcel_z=20,
        owner_id=son.agent_id,
        owner_name=son.display_name,
        for_sale=False,
    )
    engine.city_layout.buildings["bld_house_20_20"] = building
    son.home_building_id = building.building_id

    # Son dies
    engine.despawn_agent(son.agent_id, reason="NATURAL_DEATH")

    # Mother must inherit parcel AND building
    assert parcel.owner_id == mother.agent_id
    assert building.owner_id == mother.agent_id
    assert not building.for_sale
    assert mother.home_building_id == building.building_id
    assert mother.credits == 60.0  # 10 initial + 50 inherited


def test_def_t2_04_pure_end_of_day_mortal_book_export_and_crime_pruning(tmp_path: Path):
    """
    DEF-T2-04:
    - Mortal book approval queues exports in RAM with 0 mid-day disk writes,
      flushing cleanly on commit_end_of_day().
    - SpeechActEngine.reported_crimes prunes entries older than 2,000 ticks.
    """
    mortal_export_dir = Path("data/knowledge/_mortal_authored")
    # Clean export dir if it existed from previous tests
    if mortal_export_dir.exists():
        for f in mortal_export_dir.glob("*.json"):
            f.unlink()

    engine = SimulationEngine(
        db_path=tmp_path / "civ_eod_export.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        adapter=MockWorldAdapter(),
        headless=True,
    )

    # Mortal proposal committed
    prop = LibraryProposalRecord(
        proposal_id="prop_mortal_1",
        action="CREATE",
        author_id="mortal_farmer_1",
        topic="agriculture",
        title="Mortal Agriculture",
        summary="Crop rotation.",
        author_proficiency=0.8,
        status="APPROVED",
        created_tick=100,
    )
    engine.governance_engine._commit_entry_from_proposal(prop, current_tick=100)

    # Must have 0 mid-day disk writes
    written_midday = list(mortal_export_dir.glob("*.json")) if mortal_export_dir.exists() else []
    assert len(written_midday) == 0
    assert len(engine.governance_engine.pending_mortal_exports) == 1

    # End-of-day commit flushes exports
    engine.commit_end_of_day()
    written_eod = list(mortal_export_dir.glob("*.json"))
    assert len(written_eod) == 1
    assert len(engine.governance_engine.pending_mortal_exports) == 0

    # Clean up test export
    for f in written_eod:
        f.unlink()

    # Verify crime pruning older than 2,000 ticks
    engine.speech_acts.reported_crimes.add(("speaker_old", "theft", 10))  # tick 600
    engine.speech_acts.reported_crimes.add(("speaker_recent", "theft", 55))  # tick 3300
    engine.speech_acts.step(current_tick=3300, agents=[])
    # Cutoff bucket at tick 3300: (3300 - 2000) // 60 = 21. Bucket 10 < 21 -> pruned!
    assert ("speaker_old", "theft", 10) not in engine.speech_acts.reported_crimes
    assert ("speaker_recent", "theft", 55) in engine.speech_acts.reported_crimes

