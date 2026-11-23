"""
sim_core/persistence package
Atomic Two-Phase Commit checkpoints, SQLite WAL persistence, and World Goddess validation critic.
"""

from __future__ import annotations

from .checkpoints import (
    MAX_RETAINED_SNAPSHOTS,
    WorldGoddessCheckpointManager,
    compute_file_sha256,
)
from .db import (
    DDL_SCHEMA,
    execute_daily_commit,
    init_db,
    run_analytics_query,
)
from .world_goddess import WorldGoddessCritic

__all__ = [
    "DDL_SCHEMA",
    "MAX_RETAINED_SNAPSHOTS",
    "WorldGoddessCheckpointManager",
    "WorldGoddessCritic",
    "compute_file_sha256",
    "execute_daily_commit",
    "init_db",
    "run_analytics_query",
]
