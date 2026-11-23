"""
sim_core/spatial package
Spatial partitioning, terrain heightmap sampling, and navigation for Gaia.
"""

from __future__ import annotations

from .hash_grid import SpatialHashGrid
from .heightmap import Heightmap
from .navigation import (
    BuildingFootprint,
    CurtainWallObstacle,
    NavigationEngine,
)

__all__ = [
    "BuildingFootprint",
    "CurtainWallObstacle",
    "Heightmap",
    "NavigationEngine",
    "SpatialHashGrid",
]
