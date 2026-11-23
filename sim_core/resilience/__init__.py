"""
sim_core/resilience package
Self-healing error solver and fault recovery subsystems supervised by the World Goddess.
"""

from __future__ import annotations

from .healer import (
    MAX_AUTO_HEAL_PER_CLASS_PER_DAY,
    ErrorHealer,
    FaultClass,
    HealerIncidentRecord,
    HealingResult,
)

__all__ = [
    "ErrorHealer",
    "FaultClass",
    "HealerIncidentRecord",
    "HealingResult",
    "MAX_AUTO_HEAL_PER_CLASS_PER_DAY",
]
