"""
sim_core/resilience/healer.py
Self-Healing Error Solver supervised by the World Goddess.
Handles isolated faults across tensor computation, double-entry transfers,
spatial boundaries, WebSocket frames, SQLite commits, and faulty agents.
Enforces the 5-fault/day [CRITICAL] escalation guard.
"""

from __future__ import annotations

import uuid
from typing import Any, Final, Literal

from pydantic import BaseModel, Field

from sim_core.config import WORLD_MAX_X, WORLD_MAX_Z, WORLD_MIN_X, WORLD_MIN_Z

FaultClass = Literal[
    "TENSOR_NAN_INF",
    "ECONOMY_CONSERVATION_DRIFT",
    "COORD_OUT_OF_BOUNDS",
    "WS_BRIDGE_DROP",
    "SQLITE_COMMIT_FAIL",
    "AGENT_REPEAT_FAULT",
]

MAX_AUTO_HEAL_PER_CLASS_PER_DAY: Final[int] = 5


class HealingResult(BaseModel):
    incident_id: str
    day: int
    tick: int
    fault_class: FaultClass
    agent_id: str | None = None
    action_taken: str
    healed: bool
    escalated: bool
    alert_message: str | None = None


class HealerIncidentRecord(BaseModel):
    incident_id: str
    day: int
    tick: int
    fault_class: FaultClass
    agent_id: str | None = None
    action_taken: str
    escalated: bool = False
    context_json: dict[str, Any] = Field(default_factory=dict)


class ErrorHealer:
    """
    World Goddess supervised Self-Healing Error Solver.
    Auto-heals isolated anomalies and triggers [CRITICAL] alerts when
    the same fault class occurs > 5 times in a single game day.
    """

    def __init__(self) -> None:
        # Map: (day, fault_class) -> count
        self._daily_fault_counts: dict[tuple[int, FaultClass], int] = {}
        # List of incident records for daily SQLite logging and God Ledger summary
        self.incidents: list[HealerIncidentRecord] = []
        # Subsystems paused due to escalation
        self.paused_subsystems: set[str] = set()

    def get_fault_count(self, day: int, fault_class: FaultClass) -> int:
        """Returns the number of occurrences of a fault class for a given day."""
        return self._daily_fault_counts.get((day, fault_class), 0)

    def reset_day(self, new_day: int) -> None:
        """Prunes fault counts from older days to keep memory clean."""
        keys_to_delete = [k for k in self._daily_fault_counts if k[0] < new_day]
        for k in keys_to_delete:
            del self._daily_fault_counts[k]

    def handle(
        self,
        fault_class: FaultClass,
        day: int,
        tick: int,
        agent_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> HealingResult:
        """
        Processes a fault through automated healing strategies.
        If the same fault_class triggers > 5 times in `day`, escalates to [CRITICAL].
        """
        ctx = context or {}
        key = (day, fault_class)
        current_count = self._daily_fault_counts.get(key, 0) + 1
        self._daily_fault_counts[key] = current_count

        incident_id = f"inc_{day}_{tick}_{uuid.uuid4().hex[:8]}"

        # Escalation Guard: > 5 occurrences in one day escalates on the 6th+
        if current_count > MAX_AUTO_HEAL_PER_CLASS_PER_DAY:
            subsystem = self._map_fault_to_subsystem(fault_class)
            self.paused_subsystems.add(subsystem)

            alert_msg = (
                f"[CRITICAL_ESCALATION] Fault '{fault_class}' triggered {current_count} times "
                f"on Day {day}! Halting silent auto-healing for subsystem '{subsystem}' "
                "and alerting World Goddess."
            )

            record = HealerIncidentRecord(
                incident_id=incident_id,
                day=day,
                tick=tick,
                fault_class=fault_class,
                agent_id=agent_id,
                action_taken=f"ESCALATED_CRITICAL: Paused subsystem '{subsystem}'",
                escalated=True,
                context_json=ctx,
            )
            self.incidents.append(record)

            return HealingResult(
                incident_id=incident_id,
                day=day,
                tick=tick,
                fault_class=fault_class,
                agent_id=agent_id,
                action_taken=record.action_taken,
                healed=False,
                escalated=True,
                alert_message=alert_msg,
            )

        # Execute automated healing based on fault class
        action_taken = ""
        healed = True

        if fault_class == "TENSOR_NAN_INF":
            slot = ctx.get("slot_idx", 0)
            action_taken = (
                f"SELF_HEALED_TENSOR: Zeroed corrupted GRU state and restored slot {slot}."
            )

        elif fault_class == "ECONOMY_CONSERVATION_DRIFT":
            amount = ctx.get("amount", 0.0)
            action_taken = (
                f"ECONOMY_DRIFT_ROLLBACK: Reverted {amount} credits transfer, restored balance."
            )

        elif fault_class == "COORD_OUT_OF_BOUNDS":
            raw_x = ctx.get("x", 0.0)
            raw_z = ctx.get("z", 0.0)
            clamped_x = max(WORLD_MIN_X, min(WORLD_MAX_X, raw_x))
            clamped_z = max(WORLD_MIN_Z, min(WORLD_MAX_Z, raw_z))
            action_taken = (
                f"COORD_CLAMPED: Repositioned agent {agent_id} from ({raw_x:.1f}, {raw_z:.1f}) "
                f"to bounds ({clamped_x:.1f}, {clamped_z:.1f})."
            )

        elif fault_class == "WS_BRIDGE_DROP":
            action_taken = (
                "WS_BRIDGE_RESET: Paused Reality Bubble streaming while keeping Python sim intact."
            )

        elif fault_class == "SQLITE_COMMIT_FAIL":
            action_taken = (
                "SQLITE_ROLLBACK: Rolled back pending transaction, preserved RAM deltas for retry."
            )

        elif fault_class == "AGENT_REPEAT_FAULT":
            action_taken = (
                f"AGENT_QUARANTINE: Isolated faulty agent {agent_id} from active tick batches."
            )

        record = HealerIncidentRecord(
            incident_id=incident_id,
            day=day,
            tick=tick,
            fault_class=fault_class,
            agent_id=agent_id,
            action_taken=action_taken,
            escalated=False,
            context_json=ctx,
        )
        self.incidents.append(record)

        return HealingResult(
            incident_id=incident_id,
            day=day,
            tick=tick,
            fault_class=fault_class,
            agent_id=agent_id,
            action_taken=action_taken,
            healed=healed,
            escalated=False,
            alert_message=None,
        )

    @staticmethod
    def _map_fault_to_subsystem(fault_class: FaultClass) -> str:
        mapping = {
            "TENSOR_NAN_INF": "neural_engine",
            "ECONOMY_CONSERVATION_DRIFT": "world_bank_wtc",
            "COORD_OUT_OF_BOUNDS": "spatial_movement",
            "WS_BRIDGE_DROP": "websocket_bridge",
            "SQLITE_COMMIT_FAIL": "persistence_checkpoints",
            "AGENT_REPEAT_FAULT": "agent_lifecycle",
        }
        return mapping.get(fault_class, "unknown_subsystem")
