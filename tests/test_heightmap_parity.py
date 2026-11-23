"""
tests/test_heightmap_parity.py
Verifies deterministic 1024x1024 8km x 8km Concentric Open-World Heightmap:
- O(1) query performance and boundary clamping.
- Ring 0 Imperial Acropolis (32.0m palace core, 24.0m outer plaza & institutional pads).
- Ring 1 Equidistant 5 Gated Cities (r = 1,150m, 72° spacing, ~1352m chord distance, leveled pads).
- Ring 2 Frontier Wilderness (Dragon peaks, Demon caldera, carved riverbeds y < 0.0m).
- Ring 3 Great Ocean (deep ocean floor < 0.0m, beaches, outer islets).
"""

import math
from pathlib import Path

from sim_core.config import WORLD_MAX_X, WORLD_MAX_Z, WORLD_MIN_X, WORLD_MIN_Z
from sim_core.spatial.heightmap import Heightmap


def test_heightmap_concentric_world_geography():
    npy_path = Path("data/world_heightmap.npy")
    assert npy_path.exists(), "data/world_heightmap.npy must exist"

    hmap = Heightmap(npy_path)
    assert hmap.rows == 1024, f"Expected 1024 rows, got {hmap.rows}"
    assert hmap.cols == 1024, f"Expected 1024 cols, got {hmap.cols}"
    assert hmap.min_x == WORLD_MIN_X == -4000.0
    assert hmap.max_x == WORLD_MAX_X == 4000.0
    assert hmap.min_z == WORLD_MIN_Z == -4000.0
    assert hmap.max_z == WORLD_MAX_Z == 4000.0

    # -------------------------------------------------------------------------
    # 1. Ring 0 — Imperial Acropolis at (0, 0)
    # -------------------------------------------------------------------------
    h_core = hmap.get_elevation(0.0, 0.0)
    assert abs(h_core - 32.0) < 0.2, f"Palace core expected ~32.0m, got {h_core}"
    slope_core = hmap.get_slope(0.0, 0.0)
    assert slope_core < 0.05, f"Palace core should be flat, got slope {slope_core}"

    # Outer plaza institutional pads (target y = 24.0m)
    pads = [
        ("World Library", 180.0, 180.0),
        ("WTC Market", -180.0, 180.0),
        ("Courthouse", -180.0, -180.0),
        ("Cathedral", 180.0, -180.0),
    ]
    for name, px, pz in pads:
        h_pad = hmap.get_elevation(px, pz)
        assert abs(h_pad - 24.0) < 0.3, f"{name} pad expected ~24.0m, got {h_pad}"
        slope_pad = hmap.get_slope(px, pz)
        assert slope_pad < 0.05, f"{name} pad should be flat, got slope {slope_pad}"

    # -------------------------------------------------------------------------
    # 2. Ring 1 — 5 Equidistant Gated Racial Cities (r = 1,150m, 72° spacing)
    # -------------------------------------------------------------------------
    cities = [
        ("Sylvanor", 1150.0, 0.0, 28.0),
        ("Aurelia", 355.37, 1093.71, 18.0),
        ("Fenris Hold", -930.37, 675.95, 24.0),
        ("Malakor", -930.37, -675.95, 42.0),
        ("Drakonis Spire", 355.37, -1093.71, 68.0),
    ]

    for name, cx, cz, expected_h in cities:
        radius = math.sqrt(cx**2 + cz**2)
        assert abs(radius - 1150.0) < 1.0, f"{name} radius should be ~1150m, got {radius}"

        h_city = hmap.get_elevation(cx, cz)
        assert abs(h_city - expected_h) < 0.5, (
            f"{name} center expected ~{expected_h}m, got {h_city}"
        )
        slope_city = hmap.get_slope(cx, cz)
        assert slope_city < 0.05, f"{name} center should be flat, got slope {slope_city}"

    # Verify chord distance between adjacent cities is ~1,352m
    for i in range(len(cities)):
        _n1, x1, z1, _h1 = cities[i]
        _n2, x2, z2, _h2 = cities[(i + 1) % len(cities)]
        chord = math.sqrt((x2 - x1) ** 2 + (z2 - z1) ** 2)
        assert abs(chord - 1351.9) < 2.0, f"Adjacent cities should be ~1352m apart, got {chord}"

    # -------------------------------------------------------------------------
    # 3. Ring 2 — Frontier Wilderness & Natural Rivers
    # -------------------------------------------------------------------------
    # Dragon Obsidian Alpine Peaks
    h_dragon = hmap.get_elevation(2100.0, -2200.0)
    assert h_dragon > 120.0, f"Dragon peaks expected > 120m, got {h_dragon}"

    # Demon Volcanic Caldera Peak
    h_demon = hmap.get_elevation(-2400.0, -1650.0)
    assert h_demon > 120.0, f"Demon caldera expected > 120m, got {h_demon}"

    # Rivers: check riverbed points are below sea level (y < 0.0m)
    river_points = [
        ("Drakonis Run", 1400.0, -2100.0),
        ("Sylvan Brook", 2200.0, 500.0),
        ("Aurelian River", 450.0, 2700.0),
    ]
    for r_name, rx, rz in river_points:
        h_river = hmap.get_elevation(rx, rz)
        assert h_river < 0.0, f"River {r_name} at ({rx}, {rz}) should be < 0.0m, got {h_river}"

    # -------------------------------------------------------------------------
    # 4. Ring 3 — Great Ocean, Beaches & Deep Ocean Floor (r > 3,300m)
    # -------------------------------------------------------------------------
    # Deep Ocean Floor points (r > 3750m)
    deep_ocean_pts = [(0.0, 3850.0), (3850.0, 0.0), (-3850.0, 0.0), (0.0, -3850.0)]
    for ox, oz in deep_ocean_pts:
        h_ocean = hmap.get_elevation(ox, oz)
        assert h_ocean <= -20.0, f"Deep ocean at ({ox}, {oz}) should be <= -20m, got {h_ocean}"

    # Outer Islet: Northwatch Isle at (0, -3600)
    h_isle = hmap.get_elevation(0.0, -3600.0)
    assert h_isle > 5.0, f"Northwatch Isle should be above sea level, got {h_isle}"
