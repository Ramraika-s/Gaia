"""
sim_core/spatial/heightmap.py
Heightmap loader and O(1) bilinear elevation/slope query engine for Gaia.
Syncs elevation between Godot Terrain3D exported heightmap (data/world_heightmap.npy)
and Python tensor simulation core.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from sim_core.config import WORLD_MAX_X, WORLD_MAX_Z, WORLD_MIN_X, WORLD_MIN_Z


class Heightmap:
    """
    O(1) Bilinear Heightmap and Terrain Slope Query Engine.
    Operates over a 2D float32 NumPy array corresponding to world terrain elevation.
    """

    def __init__(
        self,
        file_path: str | Path | None = None,
        min_x: float = WORLD_MIN_X,
        max_x: float = WORLD_MAX_X,
        min_z: float = WORLD_MIN_Z,
        max_z: float = WORLD_MAX_Z,
        fallback_resolution: int = 512,
    ) -> None:
        self.min_x: float = float(min_x)
        self.max_x: float = float(max_x)
        self.min_z: float = float(min_z)
        self.max_z: float = float(max_z)

        self.size_x: float = self.max_x - self.min_x
        self.size_z: float = self.max_z - self.min_z

        self.data: np.ndarray

        if file_path is not None and os.path.exists(file_path):
            loaded = np.load(file_path)
            if loaded.ndim == 2:
                self.data = loaded.astype(np.float32)
            else:
                self.data = np.squeeze(loaded).astype(np.float32)
        else:
            # Fallback: Flat plane at elevation 0.0 with minimal memory overhead
            self.data = np.zeros((fallback_resolution, fallback_resolution), dtype=np.float32)

        self.rows: int = self.data.shape[0]
        self.cols: int = self.data.shape[1]

        self.scale_x: float = (self.cols - 1) / self.size_x if self.size_x > 0 else 1.0
        self.scale_z: float = (self.rows - 1) / self.size_z if self.size_z > 0 else 1.0

    def world_to_grid(self, x: float, z: float) -> tuple[float, float]:
        """Converts world coordinate (x, z) to fractional grid index (col, row)."""
        clamped_x = max(self.min_x, min(self.max_x, x))
        clamped_z = max(self.min_z, min(self.max_z, z))

        col = (clamped_x - self.min_x) * self.scale_x
        row = (clamped_z - self.min_z) * self.scale_z
        return col, row

    def get_elevation(self, x: float, z: float) -> float:
        """
        O(1) bilinear interpolation of terrain elevation at world coordinate (x, z).
        Guarantees boundary safety and zero out-of-bounds indexing.
        """
        col, row = self.world_to_grid(x, z)

        c0 = int(np.floor(col))
        r0 = int(np.floor(row))
        c1 = min(c0 + 1, self.cols - 1)
        r1 = min(r0 + 1, self.rows - 1)

        frac_c = col - c0
        frac_r = row - r0

        h00 = float(self.data[r0, c0])
        h10 = float(self.data[r0, c1])
        h01 = float(self.data[r1, c0])
        h11 = float(self.data[r1, c1])

        # Bilinear interpolation
        h_top = h00 * (1.0 - frac_c) + h10 * frac_c
        h_bot = h01 * (1.0 - frac_c) + h11 * frac_c
        return h_top * (1.0 - frac_r) + h_bot * frac_r

    def get_slope(self, x: float, z: float, step: float = 2.0) -> float:
        """
        Estimates local terrain slope magnitude (tangent of angle) in O(1) time
        using central differences.
        """
        h_east = self.get_elevation(x + step, z)
        h_west = self.get_elevation(x - step, z)
        h_north = self.get_elevation(x, z + step)
        h_south = self.get_elevation(x, z - step)

        dx = (h_east - h_west) / (2.0 * step)
        dz = (h_north - h_south) / (2.0 * step)
        return float(np.sqrt(dx * dx + dz * dz))
