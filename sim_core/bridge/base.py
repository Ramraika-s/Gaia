"""
sim_core/bridge/base.py
Abstract WorldAdapter interface defining communication contracts between the Python
simulation core and client renderers (Godot 4.7.2 or Headless Mock).
Follows ARCHITECTURE.md Section 4.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class WorldAdapter(ABC):
    """Abstract interface for world materialization, binary streaming, and discrete IPC events."""

    @abstractmethod
    def spawn_agent(self, agent_id: str, slot_idx: int, metadata: dict[str, Any]) -> None:
        """Notifies adapter that a new mortal agent has been born / spawned."""
        pass

    @abstractmethod
    def despawn_agent(self, agent_id: str, slot_idx: int, reason: str = "DEATH") -> None:
        """Notifies adapter that an agent has died or dematerialized permanently."""
        pass

    @abstractmethod
    def update_agent_position(
        self,
        slot_idx: int,
        x: float,
        y: float,
        z: float,
        yaw: float = 0.0,
        packed_flags: int = 0,
    ) -> None:
        """Updates live 3D transform and status flags for a slot."""
        pass

    @abstractmethod
    def sync_bubble(self, pooled_agents: list[dict[str, Any]]) -> None:
        """Syncs the 60-120 pooled mortals inside Godot's 3D Reality Bubble."""
        pass

    @abstractmethod
    def sync_deities(self, deities: list[dict[str, Any]]) -> None:
        """Syncs the 6 Deities' live coordinates and state over WebSocket."""
        pass

    @abstractmethod
    def sync_weather_time(
        self,
        day: int,
        time_of_day: float,
        season_progress: float,
        weather: str = "CLEAR",
        weather_details: dict[str, Any] | None = None,
    ) -> None:
        """Syncs day, Sky3D time-of-day, season shader progress, and regional weather details."""
        pass

    @abstractmethod
    def emit_event(self, event_type: str, payload: dict[str, Any]) -> None:
        """Dispatches a discrete JSON event to Godot (e.g. ALTAR_BEACON, SIGN_UPDATE)."""
        pass

    @abstractmethod
    def broadcast_event(self, event_type: str, payload: dict[str, Any]) -> None:
        """Broadcasts a discrete JSON event to all connected Godot clients."""
        pass

    @abstractmethod
    def sync_building_update(self, building: dict[str, Any] | Any) -> None:
        """Broadcasts incremental BUILDING_UPDATE event to connected clients."""
        pass

    @abstractmethod
    def broadcast_binary_frame(self, data: bytes) -> None:
        """Broadcasts packed binary coordinates for the 10,000+ Orbital God Map."""
        pass
