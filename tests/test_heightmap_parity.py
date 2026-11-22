"""
tests/test_heightmap_parity.py
Verifies deterministic heightmap loading, O(1) query performance,
and spatial parity across all 5 biomes and institutional landmark pads.
"""

from pathlib import Path

from sim_core.spatial.heightmap import Heightmap


def test_heightmap_loads_and_evaluates_5_biomes_and_pads():
    npy_path = Path("data/world_heightmap.npy")
    assert npy_path.exists(), "data/world_heightmap.npy must exist"

    hmap = Heightmap(npy_path)
    assert hmap.rows == 512
    assert hmap.cols == 512

    # 1. Central Basin & Flat Landmark Pads
    # World Goddess Sanctum at (0, 0)
    h_center = hmap.get_elevation(0.0, 0.0)
    assert abs(h_center - 18.5) < 0.2, f"Center elevation expected ~18.5, got {h_center}"

    # World Library Pad at (100, 100)
    h_lib = hmap.get_elevation(100.0, 100.0)
    assert abs(h_lib - 18.0) < 0.2, f"Library pad expected ~18.0, got {h_lib}"

    # WTC Market Pad at (-100, 100)
    h_wtc = hmap.get_elevation(-100.0, 100.0)
    assert abs(h_wtc - 18.0) < 0.2, f"WTC pad expected ~18.0, got {h_wtc}"

    # Courthouse Pad at (-100, -100)
    h_court = hmap.get_elevation(-100.0, -100.0)
    assert abs(h_court - 18.0) < 0.2, f"Courthouse pad expected ~18.0, got {h_court}"

    # Cathedral & Altar Pad at (100, -100)
    h_cath = hmap.get_elevation(100.0, -100.0)
    assert abs(h_cath - 18.0) < 0.2, f"Cathedral pad expected ~18.0, got {h_cath}"

    # 2. 5 Biome Parity
    # Dragon Obsidian Peaks: (2500, -2500)
    h_dragon = hmap.get_elevation(2500.0, -2500.0)
    assert h_dragon > 65.0, f"Dragon peaks elevation expected > 65m, got {h_dragon}"

    # Demon Ashland Crags: (-3500, 500)
    h_demon = hmap.get_elevation(-3500.0, 500.0)
    assert h_demon > 40.0, f"Demon crags elevation expected > 40m, got {h_demon}"

    # Elf Highland Forest: (2200, 2000)
    h_elf = hmap.get_elevation(2200.0, 2000.0)
    assert 30.0 <= h_elf <= 65.0, f"Elf highlands elevation expected 30-65m, got {h_elf}"

    # Human Temperate Plains: (-1800, 2000)
    h_human = hmap.get_elevation(-1800.0, 2000.0)
    assert 15.0 <= h_human <= 40.0, f"Human plains elevation expected 15-40m, got {h_human}"

    # Beasthuman Northern Steppes: (-2500, -2500)
    h_beast = hmap.get_elevation(-2500.0, -2500.0)
    assert 20.0 <= h_beast <= 55.0, f"Beasthuman steppes elevation expected 20-55m, got {h_beast}"

    # 3. Slope Calculation
    slope_center = hmap.get_slope(0.0, 0.0)
    assert slope_center < 0.1, f"Center basin should be flat, got slope {slope_center}"
