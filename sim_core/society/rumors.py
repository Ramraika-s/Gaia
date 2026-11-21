"""
sim_core/society/rumors.py
Physical rumor propagation engine.
Enforces zero telepathy; information travels through mortal encounters via bounded RumorPackets.
Follows SOCIETY_AND_GOVERNANCE_SPEC.md Section 1.2.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from sim_core.config import TICKS_PER_GAME_DAY

MAX_RUMORS_PER_AGENT = 12
CREDIBILITY_DECAY_PER_HOP = 0.90
MIN_CREDIBILITY_EXPIRY = 0.20
INTERACTION_RUMOR_EXCHANGE_COUNT = 2


class RumorPacket(BaseModel):
    """Discrete information packet traveling physically between mortal agents."""
    rumor_id: str = Field(default_factory=lambda: f"rumor_{uuid.uuid4().hex[:8]}")
    topic: str
    content: str
    origin_tick: int
    origin_parcel: str
    salience: float = Field(default=0.5, ge=0.0, le=1.0)
    credibility: float = Field(default=1.0, ge=0.0, le=1.0)
    hops: int = 0

    def decay_hop(self) -> RumorPacket:
        """Returns a new packet decayed by one physical propagation hop."""
        return RumorPacket(
            rumor_id=self.rumor_id,
            topic=self.topic,
            content=self.content,
            origin_tick=self.origin_tick,
            origin_parcel=self.origin_parcel,
            salience=self.salience,
            credibility=round(self.credibility * CREDIBILITY_DECAY_PER_HOP, 4),
            hops=self.hops + 1,
        )

    def is_expired(self, current_tick: int) -> bool:
        """Expires after 1 game day or when credibility drops below threshold."""
        if self.credibility < MIN_CREDIBILITY_EXPIRY:
            return True
        if current_tick - self.origin_tick > TICKS_PER_GAME_DAY:
            return True
        return False


class RumorNetwork:
    """Maintains per-agent RAM ring buffers of active rumors and handles physical exchanges."""

    def __init__(self, max_per_agent: int = MAX_RUMORS_PER_AGENT) -> None:
        self.max_per_agent = max_per_agent
        # agent_id -> list[RumorPacket]
        self.agent_buffers: dict[str, list[RumorPacket]] = {}

    def spawn_rumor(
        self,
        topic: str,
        content: str,
        origin_tick: int,
        origin_parcel: str,
        salience: float = 0.8,
        witness_ids: list[str] | None = None,
    ) -> RumorPacket:
        """Creates a new rumor and seeds it to witnesses."""
        packet = RumorPacket(
            topic=topic,
            content=content,
            origin_tick=origin_tick,
            origin_parcel=origin_parcel,
            salience=salience,
            credibility=1.0,
            hops=0,
        )
        if witness_ids:
            for w_id in witness_ids:
                self.add_rumor_to_agent(w_id, packet)
        return packet

    def add_rumor_to_agent(self, agent_id: str, packet: RumorPacket) -> bool:
        """Adds or updates a rumor in an agent's buffer, maintaining max capacity."""
        buf = self.agent_buffers.setdefault(agent_id, [])

        # Check existing
        for idx, existing in enumerate(buf):
            if existing.rumor_id == packet.rumor_id:
                if packet.credibility > existing.credibility:
                    buf[idx] = packet
                    return True
                return False

        buf.append(packet)
        # Sort by salience * credibility descending
        buf.sort(key=lambda r: r.salience * r.credibility, reverse=True)
        if len(buf) > self.max_per_agent:
            del buf[self.max_per_agent:]
        return True

    def exchange_rumors(
        self,
        agent_a: str,
        agent_b: str,
        dist_meters: float,
        current_tick: int,
        max_dist: float = 8.0,
    ) -> int:
        """
        Physical interaction rumor exchange:
        If within max_dist (8m), agents share their top 2 highest-salience active rumors.
        Returns total number of rumors newly learned/updated.
        """
        if dist_meters > max_dist:
            return 0

        buf_a = [r for r in self.agent_buffers.get(agent_a, []) if not r.is_expired(current_tick)]
        buf_b = [r for r in self.agent_buffers.get(agent_b, []) if not r.is_expired(current_tick)]

        shared_count = 0
        # Share top 2 from A to B
        for r_a in buf_a[:INTERACTION_RUMOR_EXCHANGE_COUNT]:
            decayed = r_a.decay_hop()
            if not decayed.is_expired(current_tick):
                if self.add_rumor_to_agent(agent_b, decayed):
                    shared_count += 1

        # Share top 2 from B to A
        for r_b in buf_b[:INTERACTION_RUMOR_EXCHANGE_COUNT]:
            decayed = r_b.decay_hop()
            if not decayed.is_expired(current_tick):
                if self.add_rumor_to_agent(agent_a, decayed):
                    shared_count += 1

        return shared_count

    def get_agent_rumors(self, agent_id: str, current_tick: int) -> list[RumorPacket]:
        """Returns non-expired rumors held by an agent."""
        buf = self.agent_buffers.get(agent_id, [])
        valid = [r for r in buf if not r.is_expired(current_tick)]
        self.agent_buffers[agent_id] = valid
        return valid

    def cleanup_expired(self, current_tick: int) -> None:
        """Prunes expired rumors across all agents."""
        for agent_id in list(self.agent_buffers.keys()):
            self.agent_buffers[agent_id] = [
                r for r in self.agent_buffers[agent_id] if not r.is_expired(current_tick)
            ]
