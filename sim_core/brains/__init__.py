"""
sim_core/brains package
4-Pillar Hybrid Cognitive Core:
- Pillar 1: SharedLivingNet (Tier 1) + ProfessionNetRegistry (Tier 2) + HierarchicalBrain (Tier 3)
- Pillar 2: MemoryRAGIndex & EpisodicMemoryRecord (Grounded RAG over world_library)
- Pillar 3: PersonalityVector & MoodState (10-D Evolving Traits & Mood Coupling)
- Pillar 4: SleepCycleConsolidator (End-of-day distillation & bounded trait drift)
"""

from __future__ import annotations

from sim_core.brains.consolidation import SleepCycleConsolidator
from sim_core.brains.hierarchical_brain import HierarchicalBrain
from sim_core.brains.memory_rag import (
    EpisodicMemoryRecord,
    MemoryRAGIndex,
)
from sim_core.brains.personality import (
    MoodState,
    PersonalityVector,
    compute_action_logit_bias,
    compute_memory_salience_weight,
    generate_personality_vector,
)
from sim_core.brains.profession_nets import (
    PROFESSIONS,
    ProfessionNet,
    ProfessionNetRegistry,
)
from sim_core.brains.shared_living_net import SharedLivingNet

__all__ = [
    "EpisodicMemoryRecord",
    "HierarchicalBrain",
    "MemoryRAGIndex",
    "MoodState",
    "PROFESSIONS",
    "PersonalityVector",
    "ProfessionNet",
    "ProfessionNetRegistry",
    "SharedLivingNet",
    "SleepCycleConsolidator",
    "compute_action_logit_bias",
    "compute_memory_salience_weight",
    "generate_personality_vector",
]
