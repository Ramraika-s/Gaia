"""
tests/brains/test_hierarchical_brain_and_actions.py
3-Tier HierarchicalBrain forward inference (< 35 ms for 10,000 agents),
knowledge-to-neural effect channel aggregation, and CognitiveActionExecutor execution.
"""

from __future__ import annotations

import time

import pytest
import torch

from sim_core.brains.action_bridge import CognitiveActionExecutor
from sim_core.brains.hierarchical_brain import HierarchicalBrain
from sim_core.brains.profession_nets import ProfessionNetRegistry, aggregate_effect_channels
from sim_core.engine import SimulationEngine
from sim_core.schemas import AgentRecord, ParcelRecord, Vec3, WorldLibraryEntry
from sim_core.society.religion import get_agent_devotion, set_agent_devotion
from sim_core.society.seasons import SeasonManager


@pytest.mark.benchmark
@pytest.mark.slow
def test_10k_agent_3tier_hierarchical_benchmark_and_zero_nan() -> None:
    """
    10,000-agent batched forward pass across 3-tier brain completes in < 35 ms on CPU
    with zero NaNs.
    """
    n_agents = 10000
    brain = HierarchicalBrain(initial_capacity=2048)
    while brain.tier3_self.capacity < n_agents:
        brain.tier3_self.grow_capacity(num_slabs=1)

    assert brain.tier3_self.capacity >= n_agents
    slot_indices = [brain.tier3_self.allocate_slot() for _ in range(n_agents)]

    x_living = torch.rand((n_agents, 24), dtype=torch.float32)
    health_ratios = torch.rand(n_agents, dtype=torch.float32)
    hungers = torch.rand(n_agents, dtype=torch.float32) * 100.0
    professions = [
        "KNIGHT",
        "CITY_GUARD",
        "FARMER",
        "MERCHANT",
        "BLACKSMITH",
        "BUILDER",
        "SCHOLAR",
        "CLERIC",
        "HUNTER",
        "CITIZEN",
    ] * 1000
    levels = [((i % 10) + 1) for i in range(n_agents)]
    active_effects = [{"defense": 0.15 if i % 2 == 0 else 0.0} for i in range(n_agents)]
    stages = ["ADULT"] * n_agents
    pers_mood_tensor = torch.full((n_agents, 15), 0.5, dtype=torch.float32)

    # Warmup
    _ = brain.forward_batch(
        slot_indices=slot_indices,
        x_living=x_living,
        professions=professions,
        levels=levels,
        active_effects=active_effects,
        stages=stages,
        personalities=pers_mood_tensor,
        moods=None,
        health_ratios=health_ratios,
        hungers=hungers,
    )

    timings: list[float] = []
    logits: torch.Tensor | None = None
    values: torch.Tensor | None = None
    for _ in range(3):
        t0 = time.perf_counter()
        logits, values = brain.forward_batch(
            slot_indices=slot_indices,
            x_living=x_living,
            professions=professions,
            levels=levels,
            active_effects=active_effects,
            stages=stages,
            personalities=pers_mood_tensor,
            moods=None,
            health_ratios=health_ratios,
            hungers=hungers,
        )
        timings.append((time.perf_counter() - t0) * 1000.0)

    elapsed_ms = min(timings)
    assert logits is not None and values is not None
    assert logits.shape == (n_agents, 20)
    assert values.shape == (n_agents, 1)
    assert torch.isfinite(logits).all()
    assert torch.isfinite(values).all()
    assert elapsed_ms < 35.0, f"Benchmark exceeded budget: {elapsed_ms:.2f} ms"


def test_aggregate_effect_channels_and_bounds_mapping() -> None:
    """
    Verifies that aggregate_effect_channels maps legacy and canonical keys into
    6 clamped channels.
    """
    assert aggregate_effect_channels({}) == (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    legacy = {
        "defense": 0.4,
        "yield_mult": 0.3,
        "trade_margin": 0.2,
        "research_rate": 0.5,
        "faith_gain": 0.6,
        "stamina_efficiency": 0.7,
    }
    assert aggregate_effect_channels(legacy) == (0.4, 0.3, 0.2, 0.5, 0.6, 0.7)

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
    assert abs(ch0 - 0.5) < 1e-5
    assert abs(ch1 - 0.4) < 1e-5
    assert abs(ch2 - 0.1) < 1e-5
    assert abs(ch3 - 0.35) < 1e-5
    assert abs(ch4 - 0.45) < 1e-5
    assert abs(ch5 - 0.7) < 1e-5

    overflow = {
        "defense": 5.0,
        "yield_mult": -10.0,
        "trade_margin": 2.5,
        "research_rate": -3.0,
        "faith_gain": 1.5,
        "stamina_efficiency": -2.0,
    }
    c_ch0, c_ch1, c_ch2, c_ch3, c_ch4, c_ch5 = aggregate_effect_channels(overflow)
    assert (c_ch0, c_ch1, c_ch2, c_ch3, c_ch4, c_ch5) == (1.0, -1.0, 1.0, -1.0, 1.0, -1.0)


def test_profession_net_pack_and_hierarchical_brain_forward() -> None:
    """pack_profession_features and HierarchicalBrain pass aggregated effects into [22:28]."""
    base_features = [0.5] * 20
    effects = {"defense_bonus": 0.3, "combat_power_multiplier": 0.2, "crop_yield_bonus": 0.4}

    packed = ProfessionNetRegistry.pack_profession_features(
        base_living_features=base_features,
        level=3,
        xp=150.0,
        active_mechanical_effects=effects,
    )
    assert len(packed) == 28
    assert abs(packed[22] - 0.5) < 1e-5
    assert abs(packed[23] - 0.4) < 1e-5

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
    assert torch.isfinite(masked_logits).all()
    assert torch.isfinite(values).all()


def test_action_bridge_need_recovery_xp_and_rollouts(engine: SimulationEngine) -> None:
    """CognitiveActionExecutor executes winning actions and captures rollouts for Lv 6+."""
    executor = CognitiveActionExecutor(engine=engine)

    a_rest = engine.spawn_agent(race="HUMAN", gender="BOY", stage="ADULT")
    a_rest.fatigue = 0.8
    a_rest.stamina = 20.0

    a_eat = engine.spawn_agent(race="ELF", gender="GIRL", stage="ADULT")
    a_eat.hunger = 40.0

    a_groom = engine.spawn_agent(race="BEASTHUMAN", gender="BOY", stage="ADULT")
    a_groom.hygiene = 0.2

    a_artisan = engine.spawn_agent(
        race="BEASTHUMAN", gender="GIRL", sub_lineage="DWARF", stage="ADULT"
    )
    a_artisan.profession = "BLACKSMITH"
    a_artisan.profession_level = 6
    a_artisan.profession_xp = 598.0
    a_artisan.active_mechanical_effects = {"craft_speed_bonus": 0.5}

    a_pray = engine.spawn_agent(race="DEMON", gender="GIRL", stage="ADULT")
    a_pray.patron_godmother_slot = "gm_demon"
    set_agent_devotion(a_pray, 0.4)

    agents = [a_rest, a_eat, a_groom, a_artisan, a_pray]
    logits = torch.full((5, 20), -1e9)
    logits[0, 0] = 10.0
    logits[1, 1] = 10.0
    logits[2, 2] = 10.0
    logits[3, 7] = 10.0
    logits[4, 9] = 10.0
    values = torch.zeros(5, 1)

    winning = executor.execute_actions(agents, logits, values)
    assert winning == [0, 1, 2, 7, 9]

    assert a_rest.fatigue < 0.8
    assert a_rest.stamina > 20.0
    assert a_eat.hunger > 40.0
    assert a_groom.hygiene > 0.2

    assert a_artisan.profession_xp > 598.0
    assert a_artisan.profession_level == 7

    assert get_agent_devotion(a_pray) > 0.4
    assert engine.divine_hierarchy.entities["gm_demon"].divine_energy > 0.0

    rollouts = executor.rollout_buffer.get_rollouts("BLACKSMITH")
    assert len(rollouts) == 1
    assert rollouts[0].level >= 6.0


def test_action_bridge_comfort_crying_child(engine: SimulationEngine) -> None:
    """Action 5 (COMFORT_CHILD) finds nearby crying child and reduces distress."""
    executor = CognitiveActionExecutor(engine=engine)
    mother = engine.spawn_agent(
        race="HUMAN", gender="GIRL", stage="ADULT", pos=Vec3(x=10.0, y=0.0, z=10.0)
    )
    infant = engine.spawn_agent(
        race="HUMAN", gender="BOY", stage="INFANT", pos=Vec3(x=11.0, y=0.0, z=10.0)
    )
    infant.crying = True
    infant.distress = 0.8
    infant.parent_ids = [mother.agent_id]

    logits = torch.full((1, 20), -1e9)
    logits[0, 5] = 10.0
    values = torch.zeros(1, 1)

    executor.execute_actions([mother], logits, values)
    assert infant.distress < 0.8


def test_study_book_proximity_and_parcel_library(engine: SimulationEngine) -> None:
    """
    Wilderness scholar cannot study remotely; studying requires proximity to library
    or parcel.
    """
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

    # 1. Distant wilderness scholar (2500m)
    wild_scholar = engine.spawn_agent(
        race="HUMAN", gender="BOY", stage="ADULT", pos=Vec3(x=2500.0, y=0.0, z=2500.0)
    )
    wild_scholar.profession = "SCHOLAR"

    logits = torch.full((1, 20), -1e9)
    logits[0, 6] = 10.0  # STUDY_BOOK
    values = torch.zeros(1, 1)

    executor.execute_actions([wild_scholar], logits, values)
    assert "ancient_tactics" not in wild_scholar.known_books
    assert wild_scholar.profession_xp == 0.0

    # 2. Acropolis Library scholar at (180.0, 0.0, 180.0)
    lib_scholar = engine.spawn_agent(
        race="HUMAN", gender="GIRL", stage="ADULT", pos=Vec3(x=180.0, y=0.0, z=180.0)
    )
    lib_scholar.profession = "SCHOLAR"
    executor.execute_actions([lib_scholar], logits, values)
    assert "ancient_tactics" in lib_scholar.known_books
    assert lib_scholar.profession_xp == 3.0

    # 3. Scholar on deeded parcel with has_library == True
    city_scholar = engine.spawn_agent(
        race="ELF", gender="GIRL", stage="ADULT", pos=Vec3(x=800.0, y=0.0, z=800.0)
    )
    city_scholar.profession = "SCHOLAR"
    cx, cz = int(800.0 // 16.0), int(800.0 // 16.0)
    engine.property_mgr.register_parcel(
        ParcelRecord(parcel_id=f"{cx}_{cz}", cx=cx, cz=cz, has_library=True)
    )

    executor.execute_actions([city_scholar], logits, values)
    assert "ancient_tactics" in city_scholar.known_books
    assert city_scholar.profession_xp == 3.0


def test_eat_city_purchase_vs_wilderness_forage(engine: SimulationEngine) -> None:
    """
    Eating in city purchases food via credits; wilderness foraging costs stamina
    and scales by season.
    """
    executor = CognitiveActionExecutor(engine=engine)
    city_agent = engine.spawn_agent(
        race="HUMAN", gender="BOY", stage="ADULT", pos=Vec3(x=50.0, y=0.0, z=50.0)
    )
    city_agent.hunger = 40.0
    city_agent.credits = 10.0
    init_bank = engine.bank.credits

    logits = torch.full((1, 20), -1e9)
    logits[0, 1] = 10.0  # EAT
    values = torch.zeros(1, 1)

    executor.execute_actions([city_agent], logits, values)
    assert city_agent.hunger == 52.0
    assert abs(city_agent.credits - 9.90) < 1e-6
    assert abs(engine.bank.credits - (init_bank + 0.10)) < 1e-6

    # Wilderness foraging
    wild_agent = engine.spawn_agent(
        race="BEASTHUMAN", gender="BOY", stage="ADULT", pos=Vec3(x=1500.0, y=0.0, z=1500.0)
    )
    wild_agent.hunger = 40.0
    wild_agent.stamina = 50.0
    wild_agent.credits = 0.0

    season_mult = SeasonManager.get_wild_food_multiplier(engine.current_season)
    executor.execute_actions([wild_agent], logits, values)
    assert wild_agent.stamina == 45.0
    assert abs(wild_agent.hunger - (40.0 + 4.0 * season_mult)) < 1e-4

    # Exhausted agent (< 5.0 stamina) cannot forage
    tired = engine.spawn_agent(
        race="BEASTHUMAN", gender="GIRL", stage="ADULT", pos=Vec3(x=1500.0, y=0.0, z=1500.0)
    )
    tired.hunger = 30.0
    tired.stamina = 3.0
    tired.credits = 0.0
    executor.execute_actions([tired], logits, values)
    assert tired.hunger == 30.0
    assert tired.stamina == 3.0


def test_pray_slot_none_and_xp_clamp(engine: SimulationEngine) -> None:
    """PRAY routes divine energy, slot_idx=None runs safely, and Lv 10 XP clamps at 1000.0."""
    executor = CognitiveActionExecutor(engine=engine)
    priest = engine.spawn_agent(race="HUMAN", gender="GIRL", stage="ADULT")
    priest.patron_godmother_slot = "gm_human"
    init_energy = engine.divine_hierarchy.entities["gm_human"].divine_energy

    logits = torch.full((1, 20), -1e9)
    logits[0, 9] = 10.0
    values = torch.zeros(1, 1)
    executor.execute_actions([priest], logits, values)
    assert engine.divine_hierarchy.entities["gm_human"].divine_energy > init_energy

    # slot_idx=None handled safely
    orphan = engine.spawn_agent(race="ELF", gender="BOY", stage="ADULT")
    orphan.slot_idx = None  # type: ignore[assignment]
    masked_logits, vals = engine.hierarchical_brain.forward_agents([orphan])
    assert masked_logits.shape == (1, 20)

    # Lv 10 artisan XP clamps at 1000.0
    artisan = engine.spawn_agent(race="HUMAN", gender="BOY", stage="ADULT")
    artisan.profession = "BLACKSMITH"
    artisan.profession_level = 10
    artisan.profession_xp = 999.5
    logits[0, 7] = 10.0
    executor.execute_actions([artisan], logits, values)
    assert artisan.profession_xp == 1000.0
