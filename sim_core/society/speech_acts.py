"""
sim_core/society/speech_acts.py
Semantic Speech Acts Engine extending physical 8m Rumor Packets.
Follows Gaia v4.0 Sprint 5 specifications:
- Structured SpeechActRecord: GREET, WARN_PRICE_SPIKE, TRADE_OFFER, SHARE_BOOK_LORE,
  REPORT_CRIME, PRAYER_CALL, COURT, POLITICAL_DEBATE.
- Real mechanical consequences:
  - SHARE_BOOK_LORE invokes teach_knowledge() on apprentice.
  - REPORT_CRIME alerts guards/knights and logs to judiciary.
  - WARN_PRICE_SPIKE logs episodic memory to MemoryRAGIndex.
  - GREET / COURT adjusts pairwise affinity.
- Streams short_utterance strings to BUBBLE_SYNC for visible mortals.
"""

from __future__ import annotations

import math
import random
import uuid
from typing import TYPE_CHECKING

from sim_core.brains.memory_rag import EpisodicMemoryRecord
from sim_core.schemas import AgentRecord, SpeechActRecord, SpeechActType

if TYPE_CHECKING:
    from sim_core.engine import SimulationEngine

PHYSICAL_SPEECH_RADIUS = 8.0  # 8 meters physical acoustic range


class SpeechActEngine:
    """
    Manages semantic speech acts between mortals and broadcasts diegetic utterances.
    """

    def __init__(self, engine: SimulationEngine | None = None) -> None:
        self.engine = engine
        self.active_utterances: dict[str, tuple[str, int]] = {}  # agent_id -> (text, expiry_tick)
        self.recent_acts: list[SpeechActRecord] = []

    def generate_utterance(
        self,
        speaker: AgentRecord,
        act_type: SpeechActType,
        topic: str = "",
        value: float = 0.0,
    ) -> str:
        """Produces compact fantasy utterances matching racial/profession tone."""
        name = speaker.display_name
        prof = speaker.profession

        if act_type == "GREET":
            if speaker.race == "ELF":
                return f"Grace upon your path, traveler. I am {name}."
            elif speaker.race == "DEMON":
                return f"Watch your step around me, {prof.lower()}."
            elif speaker.race == "DRAGON":
                return "Stand tall under the skies, mortal."
            elif speaker.race == "BEASTHUMAN":
                return "Good hunting to you, kin!"
            return "Good day, friend! Safe travels."

        elif act_type == "WARN_PRICE_SPIKE":
            commodity = topic or "Grain"
            pct = int(value * 100) if value > 0 else 25
            return f"Heed my word! {commodity} prices jumped {pct}% at the market!"

        elif act_type == "TRADE_OFFER":
            item = topic or "handcrafted goods"
            return f"Fine {item} for sale! Fair coin for honest craft."

        elif act_type == "SHARE_BOOK_LORE":
            book_title = topic or "the ancient scrolls"
            return f"The scripture of '{book_title}' reveals true discipline. Let me teach you."

        elif act_type == "REPORT_CRIME":
            crime = topic or "theft"
            return f"Guards! A criminal disturbance here — witness this {crime}!"

        elif act_type == "PRAYER_CALL":
            return "Kneel before the Divine Mother! Give thanks for this daylight."

        elif act_type == "COURT":
            return "Your eyes carry the light of stars, gentle one."

        elif act_type == "POLITICAL_DEBATE":
            return "The council must reform the harvest tariffs! We cannot endure this tax."

        return f"Greetings from {name}."

    def emit_speech_act(
        self,
        speaker: AgentRecord,
        act_type: SpeechActType,
        topic: str = "",
        value: float = 0.0,
        listener: AgentRecord | None = None,
        tick: int = 0,
    ) -> SpeechActRecord:
        """
        Emits a structured speech act from speaker, setting short_utterance
        and applying mechanical effects to eligible listeners within 8m.
        """
        utterance = self.generate_utterance(speaker, act_type, topic, value)
        speech_id = f"speech_{uuid.uuid4().hex[:10]}"

        act = SpeechActRecord(
            speech_id=speech_id,
            speaker_id=speaker.agent_id,
            speaker_name=speaker.display_name,
            listener_id=listener.agent_id if listener else None,
            act_type=act_type,
            topic=topic,
            value=value,
            sentiment=0.3 if act_type in ("GREET", "COURT", "SHARE_BOOK_LORE") else -0.2,
            trust_weight=0.7 if speaker.profession in ("SCHOLAR", "KNIGHT", "CLERIC") else 0.5,
            tick=tick,
            short_utterance=utterance,
        )

        # Set speech on speaker for Godot bubble sync (lasts 8 ticks / 4 real seconds)
        speaker.speech_text = utterance
        self.active_utterances[speaker.agent_id] = (utterance, tick + 8)
        self.recent_acts.append(act)
        if len(self.recent_acts) > 100:
            self.recent_acts.pop(0)

        # Apply consequences to listener(s)
        targets: list[AgentRecord] = []
        if listener:
            targets = [listener]
        elif self.engine:
            # Find all mortals within 8 meters
            nearby_ids = self.engine.spatial_grid.get_nearby_ids(
                speaker.pos.x, speaker.pos.z, radius=PHYSICAL_SPEECH_RADIUS
            )
            for nid in nearby_ids:
                if nid != speaker.agent_id and nid in self.engine.agents:
                    targets.append(self.engine.agents[nid])

        self._apply_mechanical_consequences(act, speaker, targets)
        return act

    def _apply_mechanical_consequences(
        self,
        act: SpeechActRecord,
        speaker: AgentRecord,
        listeners: list[AgentRecord],
    ) -> None:
        """Applies real game-state consequences based on speech act type."""
        for listener in listeners:
            dist = math.hypot(listener.pos.x - speaker.pos.x, listener.pos.z - speaker.pos.z)
            if dist > PHYSICAL_SPEECH_RADIUS:
                continue

            if act.act_type == "SHARE_BOOK_LORE":
                # Mechanical Effect: Invoke teach_knowledge() if book is in speaker's known_books
                if self.engine and act.topic in speaker.known_books:
                    self.engine.memory_rag.teach_knowledge(
                        mentor=speaker,
                        apprentice=listener,
                        entry_id=act.topic,
                        world_library=self.engine.governance_engine.library_entries,
                        current_day=self.engine.current_day,
                        current_tick=act.tick,
                    )

            elif act.act_type == "REPORT_CRIME":
                # Mechanical Effect: Alerts Knights/Guards, triggers INTERCEPT_CRIME
                if listener.profession in ("KNIGHT", "CITY_GUARD", "PALACE_KNIGHT"):
                    listener.activity_state = "INTERCEPT_CRIME"
                    # Log crime evidence in Judiciary
                    if self.engine:
                        self.engine.judiciary.file_case(
                            accused_id="suspect_unidentified",
                            offense_type="THEFT",
                            opened_tick=act.tick,
                            settlement_id=None,
                            evidence_score=0.85,
                        )

            elif act.act_type == "WARN_PRICE_SPIKE":
                # Mechanical Effect: Writes episodic memory in listener's MemoryRAGIndex
                if self.engine:
                    mem = EpisodicMemoryRecord(
                        agent_id=listener.agent_id,
                        day=self.engine.current_day,
                        tick=act.tick,
                        event_type="PRICE_SPIKE_HEARD",
                        actor_ids=[speaker.agent_id],
                        summary=f"Heard from {speaker.display_name}: {act.short_utterance}",
                        emotional_valence=-0.4,
                        tags=["COMMERCE", "PRICE_SPIKE", act.topic or "MARKET"],
                        importance=0.65,
                    )
                    self.engine.memory_rag.add_episodic_memory(listener.agent_id, mem)

            elif act.act_type in ("GREET", "COURT"):
                # Mechanical Effect: Pairwise relationship affinity boost
                if self.engine is not None:
                    delta = 0.15 if act.act_type == "COURT" else 0.05
                    self.engine.morality.record_interaction(
                        actor_id=speaker.agent_id,
                        target_id=listener.agent_id,
                        affinity_delta=delta,
                        trust_delta=0.03,
                    )

            elif act.act_type == "PRAYER_CALL":
                # Mechanical Effect: Elevates faith devotion slightly
                if hasattr(listener, "skills"):
                    cur_faith = listener.skills.get("faith_devotion", 0.5)
                    listener.skills["faith_devotion"] = min(1.0, cur_faith + 0.02)

    def step(self, current_tick: int, agents: list[AgentRecord]) -> None:
        """Clears expired speech utterances and triggers organic chatter."""
        # 1. Clear expired speech texts
        expired_ids = [
            aid for aid, (_, exp) in self.active_utterances.items() if current_tick >= exp
        ]
        for aid in expired_ids:
            del self.active_utterances[aid]
            if self.engine and aid in self.engine.agents:
                self.engine.agents[aid].speech_text = ""

        # 2. Organic Chatter Sample (1-2 pairs per tick among scheduled agents)
        if len(agents) < 2 or not self.engine:
            return

        # Check for evening socializing or marketplace conversations
        candidates = [
            a for a in agents if a.activity_state in ("SOCIALIZING", "TRADING", "STUDYING")
        ]
        if len(candidates) >= 2 and random.random() < 0.25:
            speaker = random.choice(candidates)
            # Find nearest neighbor
            nearby_ids = self.engine.spatial_grid.get_nearby_ids(
                speaker.pos.x, speaker.pos.z, radius=PHYSICAL_SPEECH_RADIUS
            )
            for nid in nearby_ids:
                if nid != speaker.agent_id and nid in self.engine.agents:
                    listener = self.engine.agents[nid]
                    # Select act based on context
                    if speaker.profession == "SCHOLAR" and speaker.known_books:
                        self.emit_speech_act(
                            speaker,
                            "SHARE_BOOK_LORE",
                            topic=speaker.known_books[0],
                            listener=listener,
                            tick=current_tick,
                        )
                    elif speaker.profession == "MERCHANT":
                        self.emit_speech_act(
                            speaker,
                            "WARN_PRICE_SPIKE",
                            topic="Wheat",
                            value=0.25,
                            listener=listener,
                            tick=current_tick,
                        )
                    else:
                        self.emit_speech_act(
                            speaker,
                            "GREET",
                            listener=listener,
                            tick=current_tick,
                        )
                    break
