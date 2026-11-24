"""
tests/brains/test_consolidation_and_rag.py
Grounded Memory RAG Index, strict knowledge asymmetry, personality-memory salience coupling,
sleep-cycle consolidation with stability-gated rollback, and bounded deity trait drift.
"""

from __future__ import annotations

import pytest
import torch

from sim_core.brains.action_bridge import ProfessionRolloutBuffer
from sim_core.brains.consolidation import SleepCycleConsolidator
from sim_core.brains.memory_rag import EpisodicMemoryRecord, MemoryRAGIndex
from sim_core.brains.personality import (
    MoodState,
    PersonalityVector,
    compute_action_logit_bias,
)
from sim_core.brains.profession_nets import ProfessionNetRegistry
from sim_core.schemas import AgentRecord, DivineEntityRecord, WorldLibraryEntry


def test_information_asymmetry_and_organic_knowledge_diffusion() -> None:
    """
    Unread books grant zero effects; studying unlocks mechanical effects;
    mentor can teach apprentice.
    """
    rag = MemoryRAGIndex()
    world_library: dict[str, WorldLibraryEntry] = {
        "tac_001_shield_interlock": WorldLibraryEntry(
            entry_id="tac_001_shield_interlock",
            topic="MILITARY_TACTICS",
            title="Imperial Phalanx Interlock",
            summary="Interlocking heavy pavise shields increases kinetic deflection.",
            author_id="palace_general_01",
            author_proficiency=0.9,
            skill_bonus=0.10,
            created_tick=100,
            tags=["MILITARY", "DEFENSE", "SHIELD"],
            mechanical_effects={"defense": 0.25, "stamina_efficiency": 0.15},
        )
    }

    knight_a = AgentRecord(
        agent_id="knight_solis_01",
        slot_idx=0,
        display_name="Gareth",
        dynasty_surname="Vanguard",
        gender="BOY",
        race="HUMAN",
        profession="KNIGHT",
        profession_level=5,
        known_books=[],
        active_mechanical_effects={},
    )

    # 1. Unread knight receives 0 defense bonus in features
    feats_unread = ProfessionNetRegistry.pack_profession_features(
        base_living_features=[0.5] * 20,
        level=knight_a.profession_level,
        xp=100.0,
        active_mechanical_effects=knight_a.active_mechanical_effects,
    )
    assert feats_unread[22] == 0.0

    # RAG query returns empty due to information asymmetry
    found_books = rag.query_library(knight_a, "shield phalanx defense", world_library)
    assert len(found_books) == 0

    # 2. Knight studies book
    ok, _ = rag.study_library_entry(knight_a, "tac_001_shield_interlock", world_library)
    assert ok is True
    assert "tac_001_shield_interlock" in knight_a.known_books
    assert knight_a.active_mechanical_effects.get("defense") == 0.25

    feats_read = ProfessionNetRegistry.pack_profession_features(
        base_living_features=[0.5] * 20,
        level=knight_a.profession_level,
        xp=100.0,
        active_mechanical_effects=knight_a.active_mechanical_effects,
    )
    assert feats_read[22] == 0.25

    found_after = rag.query_library(knight_a, "shield phalanx defense", world_library)
    assert len(found_after) == 1

    # 3. Mentor teaches apprentice
    apprentice = AgentRecord(
        agent_id="knight_apprentice_02",
        slot_idx=1,
        display_name="Caelen",
        dynasty_surname="Vanguard",
        gender="BOY",
        race="HUMAN",
        profession="KNIGHT",
        profession_level=1,
        known_books=[],
        active_mechanical_effects={},
    )

    teach_ok, _ = rag.teach_knowledge(
        mentor=knight_a,
        apprentice=apprentice,
        entry_id="tac_001_shield_interlock",
        world_library=world_library,
    )
    assert teach_ok is True
    assert "tac_001_shield_interlock" in apprentice.known_books
    assert apprentice.active_mechanical_effects.get("defense") == 0.25

    mentor_mems = rag.get_agent_memories(knight_a.agent_id)
    assert any(m.event_type == "TEACH_KNOWLEDGE" for m in mentor_mems)


def test_personality_and_mood_coupling_action_and_memory_salience() -> None:
    """Personality & mood vectors bias action logits and memory RAG ranking salience."""
    pers_a = PersonalityVector(courage=0.9, pride=0.9, caution=0.1, empathy=0.1)
    mood_a = MoodState(angry=0.8, calm=0.1, fearful=0.0)

    pers_b = PersonalityVector(courage=0.1, pride=0.1, caution=0.9, empathy=0.9)
    mood_b = MoodState(angry=0.0, calm=0.9, fearful=0.0)

    bias_a = compute_action_logit_bias(pers_a, mood_a)
    bias_b = compute_action_logit_bias(pers_b, mood_b)

    assert bias_a[10] > bias_b[10]  # Confrontation
    assert bias_b[3] > bias_a[3]  # Evade danger
    assert bias_b[5] > bias_a[5]  # Caregiving

    rag = MemoryRAGIndex()
    agent_a = AgentRecord(
        agent_id="agent_proud_01",
        slot_idx=0,
        display_name="Aegon",
        dynasty_surname="Iron",
        gender="BOY",
        race="HUMAN",
        personality=pers_a,
        mood=mood_a,
    )
    agent_b = AgentRecord(
        agent_id="agent_gentle_02",
        slot_idx=1,
        display_name="Elena",
        dynasty_surname="Silver",
        gender="GIRL",
        race="ELF",
        personality=pers_b,
        mood=mood_b,
    )

    mem_threat = EpisodicMemoryRecord(
        agent_id="agent_proud_01",
        day=1,
        tick=10,
        event_type="CRIME",
        summary="A thief insulted and challenged my honor at the plaza tavern.",
        tags=["THREAT", "INSULT", "CRIME"],
        importance=0.7,
    )
    mem_kindness = EpisodicMemoryRecord(
        agent_id="agent_proud_01",
        day=1,
        tick=15,
        event_type="FAVOR",
        summary="An herbalist gifted soothing salve to heal my wounded kin.",
        tags=["FAVOR", "KINDNESS", "CARE"],
        importance=0.7,
    )
    rag.add_episodic_memory(agent_a.agent_id, mem_threat)
    rag.add_episodic_memory(agent_a.agent_id, mem_kindness)

    mem_threat_b = mem_threat.model_copy(update={"agent_id": agent_b.agent_id, "memory_id": "m_b1"})
    mem_kindness_b = mem_kindness.model_copy(
        update={"agent_id": agent_b.agent_id, "memory_id": "m_b2"}
    )
    rag.add_episodic_memory(agent_b.agent_id, mem_threat_b)
    rag.add_episodic_memory(agent_b.agent_id, mem_kindness_b)

    results_a = rag.query_memories(agent_a, "plaza encounter with others", current_day=1, top_k=2)
    results_b = rag.query_memories(agent_b, "plaza encounter with others", current_day=1, top_k=2)

    assert results_a[0][0].tags == ["THREAT", "INSULT", "CRIME"]
    assert results_b[0][0].tags == ["FAVOR", "KINDNESS", "CARE"]


@pytest.mark.slow
def test_sleep_cycle_consolidation_stability_rollback_and_deity_drift() -> None:
    """
    Mortal distillation updates ProfessionNet; injected NaN rolls back;
    deity drift is bounded (|delta| <= 0.03).
    """
    consolidator = SleepCycleConsolidator()
    registry = ProfessionNetRegistry()

    practitioners = [
        AgentRecord(
            agent_id=f"knight_{i}",
            slot_idx=i,
            display_name=f"Knight_{i}",
            dynasty_surname="Valiant",
            gender="BOY",
            race="HUMAN",
            profession="KNIGHT",
            profession_level=7,
            profession_xp=750.0,
            active_mechanical_effects={"defense": 0.2},
        )
        for i in range(5)
    ]

    # 1. Normal safe consolidation
    res = consolidator.consolidate_mortal_professions(practitioners, registry)
    assert res["KNIGHT"]["status"] == "UPDATED_SUCCESS"

    # 2. Stability rollback on injected NaN
    res_nan = consolidator.consolidate_mortal_professions(
        practitioners, registry, inject_nan_for_test=True
    )
    assert res_nan["KNIGHT"]["status"] in ("ROLLED_BACK_NAN_DETECTED", "ROLLED_BACK_POST_STEP_NAN")
    net = registry.get_net("KNIGHT")
    assert all(torch.isfinite(p).all() for p in net.parameters())

    # 3. Bounded deity trait drift
    deities = {
        "world_goddess": DivineEntityRecord(
            slot="world_goddess",
            bestowed_name="Gaia",
            role="WORLD_GODDESS",
            personality_vector=PersonalityVector(caution=0.5, out_group_trust=0.7, devotion=0.5),
            mood=MoodState(calm=0.8),
            covenant_rebukes=1,
        ),
        "gm_demon": DivineEntityRecord(
            slot="gm_demon",
            bestowed_name="Morvath",
            role="RACIAL_GOD_MOTHER",
            patron_race="DEMON",
            personality_vector=PersonalityVector(caution=0.7, out_group_trust=0.35, devotion=0.8),
            mood=MoodState(calm=0.6),
        ),
    }

    world_events = [{"event_type": "COVENANT_BREACH"}, {"event_type": "WAR"}] + [
        {"event_type": "PRAYER"} for _ in range(30)
    ]
    rag = MemoryRAGIndex()
    deltas = consolidator.compress_deity_memories_and_drift(
        deities, world_events, memory_rag=rag, day=2
    )

    for slot, slot_deltas in deltas.items():
        for trait, d_val in slot_deltas.items():
            assert abs(d_val) <= 0.03, f"Deity {slot} trait {trait} drift exceeded 0.03: {d_val}"

    goddess_mems = rag.get_agent_memories("world_goddess")
    assert len(goddess_mems) == 1
    assert goddess_mems[0].event_type == "DIVINE_DAILY_SUMMARY"


@pytest.mark.slow
def test_consolidation_with_real_rollouts() -> None:
    """
    SleepCycleConsolidator consumes real rollouts from ProfessionRolloutBuffer
    and clears buffer.
    """
    reg = ProfessionNetRegistry()
    consolidator = SleepCycleConsolidator()
    buffer = ProfessionRolloutBuffer()

    for _ in range(5):
        buffer.add(
            profession="FARMER",
            features=[0.5] * 28,
            level=6.0,
            action_idx=4,
            reward=0.9,
        )

    assert buffer.size("FARMER") == 5
    result = consolidator.consolidate_mortal_professions(
        agents=[],
        profession_registry=reg,
        rollout_buffer=buffer,
    )
    assert result.get("FARMER") is not None
    assert buffer.size("FARMER") == 0


def test_poisoned_rollout_rollback_pruning() -> None:
    """
    Offending rollouts are purged from ProfessionRolloutBuffer on rollback
    to prevent recurring failures.
    """
    reg = ProfessionNetRegistry()
    consolidator = SleepCycleConsolidator()
    buffer = ProfessionRolloutBuffer()

    buffer.add(
        profession="FARMER",
        features=[0.5] * 28,
        level=6.0,
        action_idx=4,
        reward=0.9,
    )
    assert buffer.size("FARMER") == 1

    result = consolidator.consolidate_mortal_professions(
        agents=[],
        profession_registry=reg,
        rollout_buffer=buffer,
        inject_nan_for_test=True,
    )
    assert result.get("FARMER", {}).get("status") == "ROLLED_BACK_NAN_DETECTED"
    assert buffer.size("FARMER") == 0
