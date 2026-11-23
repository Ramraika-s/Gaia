"""
sim_core/brains/memory_rag.py
Pillar 2: Grounded RAG Over world_library & Episodic Memory.
Follows Gaia v4.0 Sprint 4 specifications:
- 100% offline retrieval over known world_library entries (strict information asymmetry).
- Personal episodic memories (EpisodicMemoryRecord) for mortal agents & deities.
- Multi-factor ranking: semantic similarity × recency decay × importance
  × personality/mood salience.
- Organic knowledge diffusion via study_library_entry() and teach_knowledge().
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Collection, Mapping
from typing import TYPE_CHECKING, Any

import numpy as np
from pydantic import BaseModel, Field

from sim_core.brains.personality import (
    MoodState,
    PersonalityVector,
    compute_memory_salience_weight,
)
from sim_core.config import TICKS_PER_GAME_DAY
from sim_core.knowledge.dedupe import DeterministicTextEmbedder
from sim_core.knowledge.schema import KnowledgeEntry

if TYPE_CHECKING:
    from sim_core.schemas import WorldLibraryEntry


class EpisodicMemoryRecord(BaseModel):
    """
    Concrete episodic memory record stamped with day and tick.
    Represents personal experiences, interactions, trials, battles, or learnings.
    """

    memory_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str
    day: int = 1
    tick: int = 0
    event_type: str  # e.g. "TRADE", "CRIME", "COMBAT", "PRAYER", "STUDY_BOOK", "TRIAL"
    actor_ids: list[str] = Field(default_factory=list)
    summary: str
    emotional_valence: float = Field(default=0.0, ge=-1.0, le=1.0)  # -1.0 negative to +1.0 positive
    tags: list[str] = Field(default_factory=list)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    embedding: list[float] | None = None


class MemoryRAGIndex:
    """
    Fast offline Episodic Memory & World Library RAG engine.
    Uses 64-dim unit-normalized orthogonal dense projections for zero-network cosine scoring.
    """

    def __init__(self, embedder: DeterministicTextEmbedder | None = None) -> None:
        self.embedder = embedder or DeterministicTextEmbedder(
            n_features=1024, n_components=64, seed=42
        )
        # Agent episodic memories: agent_id -> list of records
        self._memories: dict[str, list[EpisodicMemoryRecord]] = {}
        # Memory embedding cache: memory_id -> np.ndarray (64,)
        self._memory_embeddings: dict[str, np.ndarray] = {}
        # World Library embedding cache: entry_id -> np.ndarray (64,)
        self._library_embeddings: dict[str, np.ndarray] = {}

    # --------------------------------------------------------------------------
    # Memory Ingestion & Indexing
    # --------------------------------------------------------------------------

    def add_episodic_memory(self, agent_id: str, record: EpisodicMemoryRecord) -> str:
        """Stores an episodic memory and computes its dense semantic embedding."""
        if agent_id not in self._memories:
            self._memories[agent_id] = []

        # Embed summary + tags
        text = f"{record.summary} {' '.join(record.tags)}"
        vec = self.embedder.embed_text(text)
        record.embedding = vec.tolist()
        self._memory_embeddings[record.memory_id] = vec
        self._memories[agent_id].append(record)
        return record.memory_id

    def index_library_entry(self, entry: WorldLibraryEntry | KnowledgeEntry) -> None:
        """Embeds a single WorldLibraryEntry or KnowledgeEntry and caches its dense vector."""
        topic = entry.subject if isinstance(entry, KnowledgeEntry) else entry.topic
        text = f"{entry.title} {topic} {entry.summary} {' '.join(entry.tags)}"
        body = getattr(entry, "body", None)
        if body:
            text += f" {body[:300]}"
        vec = self.embedder.embed_text(text)
        self._library_embeddings[entry.entry_id] = vec

    def index_library_entries(
        self, entries: Collection[WorldLibraryEntry | KnowledgeEntry]
    ) -> None:
        """Batch indexes multiple WorldLibraryEntry or KnowledgeEntry items."""
        for entry in entries:
            self.index_library_entry(entry)

    def get_agent_memories(self, agent_id: str) -> list[EpisodicMemoryRecord]:
        """Returns all raw memories for an agent."""
        return self._memories.get(agent_id, [])

    def get_recent_memories(self, agent_id: str, limit: int = 5) -> list[EpisodicMemoryRecord]:
        """Returns the most recent memories for an agent up to limit."""
        mems = self._memories.get(agent_id, [])
        return mems[-limit:] if limit > 0 else mems

    # --------------------------------------------------------------------------
    # Episodic Memory Retrieval
    # --------------------------------------------------------------------------

    def query_memories(
        self,
        agent: Any,
        query_text: str,
        current_day: int = 1,
        current_tick: int = 0,
        top_k: int = 5,
        half_life_days: float = 20.0,
    ) -> list[tuple[EpisodicMemoryRecord, float]]:
        """
        Retrieves top_k episodic memories for `agent` using blended multi-factor ranking:
        score = semantic_sim * recency_decay * importance * personality_salience
        """
        agent_id = getattr(agent, "agent_id", str(agent))
        records = self._memories.get(agent_id, [])
        if not records:
            return []

        query_vec = self.embedder.embed_text(query_text)
        personality: PersonalityVector | None = getattr(agent, "personality", None)
        mood: MoodState | None = getattr(agent, "mood", None)

        scored_records: list[tuple[EpisodicMemoryRecord, float]] = []

        for rec in records:
            # 1. Semantic similarity (cosine between unit vectors)
            rec_vec = self._memory_embeddings.get(rec.memory_id)
            if rec_vec is None:
                if rec.embedding:
                    rec_vec = np.array(rec.embedding, dtype=np.float32)
                else:
                    rec_vec = self.embedder.embed_text(rec.summary)
                self._memory_embeddings[rec.memory_id] = rec_vec

            cosine_sim = float(np.dot(query_vec, rec_vec))
            # Clamp to [0.01, 1.0] to prevent non-negative cancellation
            sim_factor = max(0.01, (cosine_sim + 1.0) / 2.0)

            # 2. Recency decay (exponential half-life decay)
            day_delta = max(0, current_day - rec.day)
            tick_delta = max(0, current_tick - rec.tick)
            total_days_ago = day_delta + (tick_delta / max(1, TICKS_PER_GAME_DAY))
            recency_decay = math.exp(-math.log(2.0) * total_days_ago / max(1.0, half_life_days))

            # 3. Importance weight
            importance_factor = max(0.1, rec.importance)

            # 4. Personality & Mood salience
            salience_weight = compute_memory_salience_weight(personality, mood, rec.tags)

            final_score = sim_factor * recency_decay * importance_factor * salience_weight
            scored_records.append((rec, final_score))

        scored_records.sort(key=lambda x: x[1], reverse=True)
        return scored_records[:top_k]

    # --------------------------------------------------------------------------
    # World Library Retrieval (Grounded with Information Asymmetry)
    # --------------------------------------------------------------------------

    def query_library(
        self,
        agent: Any,
        query_text: str,
        world_library: Mapping[str, WorldLibraryEntry | KnowledgeEntry],
        top_k: int = 3,
        bypass_knowledge_filter: bool = False,
    ) -> list[tuple[WorldLibraryEntry | KnowledgeEntry, float]]:
        """
        Retrieves knowledge books relevant to `query_text`.
        Strict Information Asymmetry:
        - Mortal agents can ONLY retrieve entries in `agent.known_books`.
        - Deities and God can query all entries (bypass_knowledge_filter=True).
        """
        is_deity = getattr(agent, "is_god", False) or getattr(agent, "is_deity", False)
        known_books = set(getattr(agent, "known_books", []))

        query_vec = self.embedder.embed_text(query_text)
        personality: PersonalityVector | None = getattr(agent, "personality", None)
        mood: MoodState | None = getattr(agent, "mood", None)

        candidates: list[WorldLibraryEntry | KnowledgeEntry] = []
        for entry_id, entry in world_library.items():
            if bypass_knowledge_filter or is_deity or (entry_id in known_books):
                candidates.append(entry)

        if not candidates:
            return []

        scored_entries: list[tuple[WorldLibraryEntry | KnowledgeEntry, float]] = []
        for entry in candidates:
            entry_vec = self._library_embeddings.get(entry.entry_id)
            if entry_vec is None:
                self.index_library_entry(entry)
                entry_vec = self._library_embeddings[entry.entry_id]

            cosine_sim = float(np.dot(query_vec, entry_vec))
            sim_factor = max(0.01, (cosine_sim + 1.0) / 2.0)

            # Salience based on entry tags
            entry_topic = entry.subject if isinstance(entry, KnowledgeEntry) else entry.topic
            entry_bonus = 0.0 if isinstance(entry, KnowledgeEntry) else entry.skill_bonus
            salience_weight = compute_memory_salience_weight(
                personality, mood, [entry_topic] + entry.tags
            )

            # Proficiency / quality bonus
            quality_factor = max(0.5, 1.0 + (entry_bonus * 2.0))

            final_score = sim_factor * salience_weight * quality_factor
            scored_entries.append((entry, final_score))

        scored_entries.sort(key=lambda x: x[1], reverse=True)
        return scored_entries[:top_k]

    # --------------------------------------------------------------------------
    # Organic Knowledge Diffusion
    # --------------------------------------------------------------------------

    def study_library_entry(
        self,
        agent: Any,
        entry_id: str,
        world_library: Mapping[str, WorldLibraryEntry | KnowledgeEntry],
        current_day: int = 1,
        current_tick: int = 0,
    ) -> tuple[bool, str]:
        """
        Agent studies a book from the World Library:
        1. Checks existence in world_library.
        2. Adds to agent.known_books if not present.
        3. Activates and applies entry.mechanical_effects into agent.active_mechanical_effects.
        4. Logs an episodic memory and increments book read count.
        """
        if entry_id not in world_library:
            return False, f"ENTRY_NOT_FOUND: {entry_id}"

        entry = world_library[entry_id]

        known_books = getattr(agent, "known_books", None)
        if known_books is None:
            agent.known_books = []
            known_books = agent.known_books

        if entry_id in known_books:
            return False, f"ALREADY_KNOWN: {entry_id}"

        known_books.append(entry_id)

        # Apply mechanical effects
        active_effects = getattr(agent, "active_mechanical_effects", None)
        if active_effects is None:
            agent.active_mechanical_effects = {}
            active_effects = agent.active_mechanical_effects

        for effect_name, effect_val in entry.mechanical_effects.items():
            active_effects[effect_name] = active_effects.get(effect_name, 0.0) + float(effect_val)

        # Increment read count
        if not isinstance(entry, KnowledgeEntry):
            entry.read_count += 1

        # Award small curiosity & discipline boost or mood inspiration
        if hasattr(agent, "mood") and agent.mood is not None:
            agent.mood.inspired = min(1.0, agent.mood.inspired + 0.2)

        author_id = entry.author if isinstance(entry, KnowledgeEntry) else entry.author_id
        topic = entry.subject if isinstance(entry, KnowledgeEntry) else entry.topic

        # Log episodic memory
        mem = EpisodicMemoryRecord(
            agent_id=getattr(agent, "agent_id", "unknown"),
            day=current_day,
            tick=current_tick,
            event_type="STUDY_BOOK",
            actor_ids=[author_id],
            summary=f"Studied '{entry.title}': {entry.summary}",
            emotional_valence=0.4,
            tags=["KNOWLEDGE", "BOOK", topic] + entry.tags[:2],
            importance=0.6,
        )
        self.add_episodic_memory(mem.agent_id, mem)

        return True, f"STUDY_SUCCESS: Learned '{entry.title}'"

    def teach_knowledge(
        self,
        mentor: Any,
        apprentice: Any,
        entry_id: str,
        world_library: Mapping[str, WorldLibraryEntry | KnowledgeEntry],
        current_day: int = 1,
        current_tick: int = 0,
    ) -> tuple[bool, str]:
        """
        Mentor teaches knowledge entry to apprentice:
        1. Verifies mentor knows the entry (or is deity/god).
        2. Verifies apprentice does not already know it.
        3. Studies entry for apprentice (unlocking mechanical effects).
        4. Logs episodic memories for both mentor and apprentice.
        """
        if entry_id not in world_library:
            return False, f"ENTRY_NOT_FOUND: {entry_id}"

        entry = world_library[entry_id]

        is_mentor_deity = getattr(mentor, "is_god", False) or getattr(mentor, "is_deity", False)
        mentor_known = set(getattr(mentor, "known_books", []))
        if not is_mentor_deity and entry_id not in mentor_known:
            return False, f"MENTOR_DOES_NOT_KNOW: {entry_id}"

        apprentice_known = set(getattr(apprentice, "known_books", []))
        if entry_id in apprentice_known:
            return False, f"APPRENTICE_ALREADY_KNOWS: {entry_id}"

        # Study for apprentice
        success, msg = self.study_library_entry(
            apprentice, entry_id, world_library, current_day, current_tick
        )
        if not success:
            return False, msg

        mentor_id = getattr(mentor, "agent_id", "mentor")
        apprentice_id = getattr(apprentice, "agent_id", "apprentice")
        topic = entry.subject if isinstance(entry, KnowledgeEntry) else entry.topic

        # Mentor memory
        mentor_mem = EpisodicMemoryRecord(
            agent_id=mentor_id,
            day=current_day,
            tick=current_tick,
            event_type="TEACH_KNOWLEDGE",
            actor_ids=[apprentice_id],
            summary=f"Taught knowledge '{entry.title}' to {apprentice_id}",
            emotional_valence=0.5,
            tags=["KNOWLEDGE", "MENTORSHIP", "FAVOR", topic],
            importance=0.55,
        )
        self.add_episodic_memory(mentor_id, mentor_mem)

        return True, f"TEACH_SUCCESS: Mentored {apprentice_id} in '{entry.title}'"
