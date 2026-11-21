"""
sim_core/bridge/mock_adapter.py
Fast headless mock adapter for unit tests, multi-thousand soak tests,
and headless CI simulations.
"""

from __future__ import annotations

from typing import Any

from sim_core.bridge.base import WorldAdapter


class MockWorldAdapter(WorldAdapter):
    """Headless WorldAdapter capturing all visual, transform, and event IPC traffic in RAM."""

    def __init__(self) -> None:
        self.spawned_agents: dict[str, dict[str, Any]] = {}
        self.despawned_agents: list[tuple[str, str]] = []
        self.positions: dict[int, tuple[float, float, float, float, int]] = {}
        self.bubble_agents: list[dict[str, Any]] = []
        self.events: list[tuple[str, dict[str, Any]]] = []
        self.weather_time: dict[str, Any] = {
            "day": 1,
            "time_of_day": 0.0,
            "season_progress": 0.0,
            "weather": "CLEAR",
        }
        self.binary_frames_count: int = 0
        self.last_binary_frame_bytes: bytes = b""

    def spawn_agent(self, agent_id: str, slot_idx: int, metadata: dict[str, Any]) -> None:
        self.spawned_agents[agent_id] = {
            "slot_idx": slot_idx,
            **metadata,
        }

    def despawn_agent(self, agent_id: str, slot_idx: int, reason: str = "DEATH") -> None:
        self.despawned_agents.append((agent_id, reason))
        self.spawned_agents.pop(agent_id, None)
        self.positions.pop(slot_idx, None)

    def update_agent_position(
        self,
        slot_idx: int,
        x: float,
        y: float,
        z: float,
        yaw: float = 0.0,
        packed_flags: int = 0,
    ) -> None:
        self.positions[slot_idx] = (x, y, z, yaw, packed_flags)

    def sync_bubble(self, pooled_agents: list[dict[str, Any]]) -> None:
        self.bubble_agents = list(pooled_agents)

    def sync_weather_time(
        self,
        day: int,
        time_of_day: float,
        season_progress: float,
        weather: str = "CLEAR",
    ) -> None:
        self.weather_time = {
            "day": day,
            "time_of_day": time_of_day,
            "season_progress": season_progress,
            "weather": weather,
        }

    def emit_event(self, event_type: str, payload: dict[str, Any]) -> None:
        self.events.append((event_type, payload))

    def broadcast_binary_frame(self, data: bytes) -> None:
        self.binary_frames_count += 1
        self.last_binary_frame_bytes = data

    def clear(self) -> None:
        """Resets all captured buffers."""
        self.spawned_agents.clear()
        self.despawned_agents.clear()
        self.positions.clear()
        self.bubble_agents.clear()
        self.events.clear()
        self.binary_frames_count = 0
        self.last_binary_frame_bytes = b""
