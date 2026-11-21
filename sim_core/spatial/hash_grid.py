"""
sim_core/spatial/hash_grid.py
Vectorized 16x16m chunk spatial hash grid for the Gaia civilization engine.
Enables O(1) neighbor searches, parcel lookups, crying-infant caretaker detection,
and Reality Bubble candidate selection for 10,000+ agents.
"""

from __future__ import annotations

import math

import numpy as np

from sim_core.config import PARCEL_SIZE


class SpatialHashGrid:
    """
    High-performance 2D spatial hash grid aligned to 16x16m parcels.
    Keyed by integer grid coordinates (cx, cz).
    """

    def __init__(self, cell_size: float = PARCEL_SIZE) -> None:
        self.cell_size: float = float(cell_size)
        self.inv_cell_size: float = 1.0 / self.cell_size
        # Map: (cx, cz) -> set of agent_ids
        self._cells: dict[tuple[int, int], set[str]] = {}
        # Map: agent_id -> (cx, cz, x, z)
        self._agent_positions: dict[str, tuple[int, int, float, float]] = {}

    def get_cell_coords(self, x: float, z: float) -> tuple[int, int]:
        """Calculates chunk parcel cell coordinates (cx, cz)."""
        return int(math.floor(x * self.inv_cell_size)), int(math.floor(z * self.inv_cell_size))

    def get_parcel_id(self, x: float, z: float) -> str:
        """Returns the canonical parcel_id string f'{cx}_{cz}' aligned 1:1 to SQLite deeds."""
        cx, cz = self.get_cell_coords(x, z)
        return f"{cx}_{cz}"

    def update_agent(self, agent_id: str, x: float, z: float) -> tuple[int, int]:
        """
        Updates an individual agent's position in the spatial hash grid.
        Returns the new (cx, cz) cell coordinates.
        """
        new_cx, new_cz = self.get_cell_coords(x, z)

        if agent_id in self._agent_positions:
            old_cx, old_cz, _, _ = self._agent_positions[agent_id]
            if (old_cx, old_cz) == (new_cx, new_cz):
                self._agent_positions[agent_id] = (new_cx, new_cz, x, z)
                return new_cx, new_cz
            # Remove from old cell
            old_cell = self._cells.get((old_cx, old_cz))
            if old_cell is not None:
                old_cell.discard(agent_id)
                if not old_cell:
                    del self._cells[(old_cx, old_cz)]

        # Add to new cell
        cell = self._cells.setdefault((new_cx, new_cz), set())
        cell.add(agent_id)
        self._agent_positions[agent_id] = (new_cx, new_cz, x, z)
        return new_cx, new_cz

    def remove_agent(self, agent_id: str) -> None:
        """Removes an agent from the grid."""
        if agent_id in self._agent_positions:
            cx, cz, _, _ = self._agent_positions.pop(agent_id)
            cell = self._cells.get((cx, cz))
            if cell is not None:
                cell.discard(agent_id)
                if not cell:
                    del self._cells[(cx, cz)]

    def insert_batch(self, agent_ids: list[str], xs: np.ndarray, zs: np.ndarray) -> None:
        """
        Vectorized batch insertion/update of agents into the spatial grid.
        Optimized for 10,000+ agents.
        """
        cxs = np.floor(xs * self.inv_cell_size).astype(np.int32)
        czs = np.floor(zs * self.inv_cell_size).astype(np.int32)

        for agent_id, cx_val, cz_val, x_val, z_val in zip(
            agent_ids, cxs, czs, xs, zs, strict=False
        ):
            cx, cz = int(cx_val), int(cz_val)
            x_f, z_f = float(x_val), float(z_val)

            if agent_id in self._agent_positions:
                old_cx, old_cz, _, _ = self._agent_positions[agent_id]
                if (old_cx, old_cz) != (cx, cz):
                    old_cell = self._cells.get((old_cx, old_cz))
                    if old_cell is not None:
                        old_cell.discard(agent_id)
                        if not old_cell:
                            del self._cells[(old_cx, old_cz)]

            cell = self._cells.setdefault((cx, cz), set())
            cell.add(agent_id)
            self._agent_positions[agent_id] = (cx, cz, x_f, z_f)

    def query_radius(self, center_x: float, center_z: float, radius: float) -> list[str]:
        """
        Queries all agents within radius of (center_x, center_z) in O(1) average time.
        Uses parcel cell boundaries to narrow candidate search before exact distance check.
        """
        min_cx = int(math.floor((center_x - radius) * self.inv_cell_size))
        max_cx = int(math.floor((center_x + radius) * self.inv_cell_size))
        min_cz = int(math.floor((center_z - radius) * self.inv_cell_size))
        max_cz = int(math.floor((center_z + radius) * self.inv_cell_size))

        r2 = radius * radius
        results: list[str] = []

        for cx in range(min_cx, max_cx + 1):
            for cz in range(min_cz, max_cz + 1):
                cell = self._cells.get((cx, cz))
                if not cell:
                    continue
                for agent_id in cell:
                    _, _, ax, az = self._agent_positions[agent_id]
                    dx = ax - center_x
                    dz = az - center_z
                    if (dx * dx + dz * dz) <= r2:
                        results.append(agent_id)

        return results

    def query_cell_agents(self, cx: int, cz: int) -> set[str]:
        """Returns the set of agent_ids inside a single parcel cell."""
        return self._cells.get((cx, cz), set()).copy()

    def count(self) -> int:
        """Returns the total number of tracked agents in the grid."""
        return len(self._agent_positions)

    def clear(self) -> None:
        """Clears all grid entries."""
        self._cells.clear()
        self._agent_positions.clear()
