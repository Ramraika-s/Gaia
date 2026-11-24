# tests/world/test_heightmap_and_weather.py
from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

import numpy as np
import pytest

from sim_core.config import WORLD_MAX_X, WORLD_MAX_Z, WORLD_MIN_X, WORLD_MIN_Z
from sim_core.engine import SimulationEngine
from sim_core.schemas import Vec3
from sim_core.spatial.heightmap import Heightmap
from sim_core.world.regional_weather import RegionalWeatherEngine


def _load_png_grayscale(filename: Path) -> np.ndarray:
    """Decodes an 8-bit grayscale PNG file into a numpy array (H, W)."""
    with open(filename, "rb") as f:
        data = f.read()

    offset = 8
    width, height = 0, 0
    idat_chunks: list[bytes] = []
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        tag = data[offset + 4 : offset + 8]
        chunk_data = data[offset + 8 : offset + 8 + length]
        if tag == b"IHDR":
            width, height = struct.unpack(">II", chunk_data[:8])
        elif tag == b"IDAT":
            idat_chunks.append(chunk_data)
        offset += 12 + length

    decompressed = zlib.decompress(b"".join(idat_chunks))
    stride = 1 + width
    img = np.zeros((height, width), dtype=np.uint8)
    for r in range(height):
        row_raw = decompressed[r * stride + 1 : (r + 1) * stride]
        img[r] = np.frombuffer(row_raw, dtype=np.uint8)
    return img


def _load_png_rgba(filename: Path) -> np.ndarray:
    """Decodes an 8-bit RGBA PNG file into a numpy array (H, W, 4)."""
    with open(filename, "rb") as f:
        data = f.read()

    offset = 8
    width, height = 0, 0
    idat_chunks: list[bytes] = []
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        tag = data[offset + 4 : offset + 8]
        chunk_data = data[offset + 8 : offset + 8 + length]
        if tag == b"IHDR":
            width, height = struct.unpack(">II", chunk_data[:8])
        elif tag == b"IDAT":
            idat_chunks.append(chunk_data)
        offset += 12 + length

    decompressed = zlib.decompress(b"".join(idat_chunks))
    stride = 1 + width * 4
    img = np.zeros((height, width, 4), dtype=np.uint8)
    for r in range(height):
        row_raw = decompressed[r * stride + 1 : (r + 1) * stride]
        img[r] = np.frombuffer(row_raw, dtype=np.uint8).reshape((width, 4))
    return img


def test_heightmap_concentric_world_geography() -> None:
    npy_path = Path("data/world_heightmap.npy")
    assert npy_path.exists(), "data/world_heightmap.npy must exist"

    hmap = Heightmap(npy_path)
    assert hmap.rows == 1024, f"Expected 1024 rows, got {hmap.rows}"
    assert hmap.cols == 1024, f"Expected 1024 cols, got {hmap.cols}"
    assert hmap.min_x == WORLD_MIN_X == -4000.0
    assert hmap.max_x == WORLD_MAX_X == 4000.0
    assert hmap.min_z == WORLD_MIN_Z == -4000.0
    assert hmap.max_z == WORLD_MAX_Z == 4000.0

    # 1. Ring 0 — Imperial Acropolis at (0, 0)
    h_core = hmap.get_elevation(0.0, 0.0)
    assert abs(h_core - 32.0) < 0.2, f"Palace core expected ~32.0m, got {h_core}"
    slope_core = hmap.get_slope(0.0, 0.0)
    assert slope_core < 0.05, f"Palace core should be flat, got slope {slope_core}"

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

    # 2. Ring 1 — 5 Equidistant Gated Racial Cities (r = 1,150m, 72° spacing)
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

    for i in range(len(cities)):
        _n1, x1, z1, _h1 = cities[i]
        _n2, x2, z2, _h2 = cities[(i + 1) % len(cities)]
        chord = math.sqrt((x2 - x1) ** 2 + (z2 - z1) ** 2)
        assert abs(chord - 1351.9) < 2.0, f"Adjacent cities should be ~1352m apart, got {chord}"

    # 3. Ring 2 — Frontier Wilderness & Natural Rivers
    h_dragon = hmap.get_elevation(2100.0, -2200.0)
    assert h_dragon > 120.0, f"Dragon peaks expected > 120m, got {h_dragon}"

    h_demon = hmap.get_elevation(-2400.0, -1650.0)
    assert h_demon > 120.0, f"Demon caldera expected > 120m, got {h_demon}"

    river_points = [
        ("Drakonis Run", 1400.0, -2100.0),
        ("Sylvan Brook", 2200.0, 500.0),
        ("Aurelian River", 450.0, 2700.0),
    ]
    for r_name, rx, rz in river_points:
        h_river = hmap.get_elevation(rx, rz)
        assert h_river < 0.0, f"River {r_name} at ({rx}, {rz}) should be < 0.0m, got {h_river}"

    # 4. Ring 3 — Great Ocean, Beaches & Deep Ocean Floor (r > 3,300m)
    deep_ocean_pts = [(0.0, 3850.0), (3850.0, 0.0), (-3850.0, 0.0), (0.0, -3850.0)]
    for ox, oz in deep_ocean_pts:
        h_ocean = hmap.get_elevation(ox, oz)
        assert h_ocean <= -20.0, f"Deep ocean at ({ox}, {oz}) should be <= -20m, got {h_ocean}"

    h_isle = hmap.get_elevation(0.0, -3600.0)
    assert h_isle > 5.0, f"Northwatch Isle should be above sea level, got {h_isle}"


def test_weather_engine_initialization_and_sampling() -> None:
    engine = RegionalWeatherEngine(seed=123)
    assert len(engine.cells) >= 6

    # 1. Demon Caldera Biome Bias: (-2400, -1650) should sample predominantly ASH
    sample_demon = engine.sample_weather_at(-2400.0, -1650.0)
    assert sample_demon["primary_weather"] == "ASH"
    assert sample_demon["blend_weights"]["ASH"] >= 0.40
    assert sample_demon["fog_density"] > 0.005
    assert sample_demon["sky_tint"][0] < 0.8

    # 2. Dragon Obsidian Peaks Biome Bias: (2100, -2200) should sample SNOW
    sample_dragon = engine.sample_weather_at(2100.0, -2200.0)
    assert sample_dragon["primary_weather"] == "SNOW"
    assert sample_dragon["blend_weights"]["SNOW"] >= 0.40

    # 3. Human Sunlit Plains Biome Bias: (1200, 2000) should sample CLEAR
    sample_human = engine.sample_weather_at(1200.0, 2000.0)
    assert sample_human["primary_weather"] == "CLEAR"
    assert sample_human["blend_weights"]["CLEAR"] >= 0.40

    # 4. Ring 0 Acropolis Center at (0, 0): Valid ambient blend
    sample_center = engine.sample_weather_at(0.0, 0.0)
    assert sample_center["primary_weather"] in ["CLEAR", "OVERCAST", "RAIN"]
    weights_sum = sum(sample_center["blend_weights"].values())
    assert abs(weights_sum - 1.0) < 0.02
    assert 0.0 < sample_center["fog_density"] < 0.05
    for c in sample_center["sky_tint"]:
        assert 0.0 <= c <= 1.0


def test_weather_cell_drift_and_bounds_safety() -> None:
    engine = RegionalWeatherEngine(seed=999)
    initial_x = engine.cells[0].center_x
    initial_z = engine.cells[0].center_z

    for tick in range(1, 121):
        engine.step(current_tick=tick, season="SPRING")

    assert engine.cells[0].center_x != initial_x
    assert engine.cells[0].center_z != initial_z

    for cell in engine.cells:
        assert -4500.0 <= cell.center_x <= 4500.0
        assert -4500.0 <= cell.center_z <= 4500.0


def test_weather_seasonal_transition() -> None:
    engine = RegionalWeatherEngine(seed=42)

    engine.step(current_tick=500, season="WINTER")
    rain_cells = [c for c in engine.cells if c.weather_type == "RAIN"]
    assert len(rain_cells) == 0, "No rain cells should persist in harsh winter"

    snow_cells = [c for c in engine.cells if c.weather_type == "SNOW"]
    assert len(snow_cells) >= 2


def test_weather_sampling_at_all_5_cities() -> None:
    engine = RegionalWeatherEngine(seed=777)
    cities = [
        ("Sylvanor", 1150.0, 0.0),
        ("Aurelia", 355.37, 1093.71),
        ("Fenris Hold", -930.37, 675.95),
        ("Malakor", -930.37, -675.95),
        ("Drakonis Spire", 355.37, -1093.71),
    ]

    for name, cx, cz in cities:
        sample = engine.sample_weather_at(cx, cz)
        assert sample["primary_weather"] in [
            "CLEAR",
            "OVERCAST",
            "RAIN",
            "STORM",
            "SNOW",
            "ASH",
        ], f"City {name} returned invalid primary weather"
        w_sum = sum(sample["blend_weights"].values())
        assert abs(w_sum - 1.0) < 0.02, f"City {name} blend weights do not sum to 1.0"
        assert sample["wind_strength"] >= 0.0
        assert sample["fog_density"] > 0.0


def test_weather_anchoring_and_reversibility() -> None:
    """Verifies demon_caldera_ash stays anchored within 350m and transitions are reversible."""
    weather = RegionalWeatherEngine(seed=42)
    ash_cell = next(c for c in weather.cells if c.cell_id == "demon_caldera_ash")
    taiga_cell = next(c for c in weather.cells if c.cell_id == "beast_taiga_overcast")

    for tick in range(1, 5001):
        if tick < 1200:
            season = "SPRING"
        elif tick < 2500:
            season = "WINTER"
        elif tick < 3800:
            season = "SUMMER"
        else:
            season = "SPRING"
        weather.step(current_tick=tick, season=season)

    dist_anchor = math.hypot(ash_cell.center_x - (-2400.0), ash_cell.center_z - (-1650.0))
    assert dist_anchor <= 350.0 + 1e-3, f"Ash cell drifted {dist_anchor:.2f}m (> 350m)"
    assert ash_cell.weather_type == "ASH"

    weather.step(current_tick=5001, season="WINTER")
    assert taiga_cell.weather_type == "SNOW"

    weather.step(current_tick=5002, season="SPRING")
    assert taiga_cell.weather_type == "OVERCAST"

    weather.step(current_tick=5003, season="SUMMER")
    assert taiga_cell.weather_type == "OVERCAST"


def test_per_agent_regional_weather(engine: SimulationEngine) -> None:
    """Verifies agents at distinct world coords receive regional microclimate weather."""
    ag_malakor = engine.spawn_agent(race="DEMON", gender="BOY", stage="ADULT")
    ag_malakor.pos = Vec3(x=-2200.0, y=0.0, z=-2200.0)

    ag_drakonis = engine.spawn_agent(race="DRAGON", gender="BOY", stage="ADULT")
    ag_drakonis.pos = Vec3(x=2800.0, y=0.0, z=2800.0)

    engine.step_tick()

    weather_m = engine.weather_engine.sample_weather_at(ag_malakor.pos.x, ag_malakor.pos.z)
    weather_d = engine.weather_engine.sample_weather_at(ag_drakonis.pos.x, ag_drakonis.pos.z)

    assert weather_m.get("primary_weather") == "ASH"
    assert weather_m.get("blend_weights", {}).get("ASH", 0.0) > 0.5
    assert weather_d.get("blend_weights", {}).get("ASH", 0.0) == 0.0


def test_biome_splat_channel_normalization_and_separation() -> None:
    splat_path = Path("godot_client/assets/terrain/world_biome_splat.png")
    assert splat_path.exists(), "godot_client/assets/terrain/world_biome_splat.png must exist"

    img = _load_png_rgba(splat_path)
    assert img.shape == (1024, 1024, 4), f"Expected (1024, 1024, 4), got {img.shape}"

    def sample_splat(wx: float, wz: float) -> tuple[int, int, int, int]:
        col = int(round(((wx + 4000.0) / 8000.0) * 1023.0))
        row = int(round(((wz + 4000.0) / 8000.0) * 1023.0))
        col = max(0, min(1023, col))
        row = max(0, min(1023, row))
        pixel = img[row, col]
        return int(pixel[0]), int(pixel[1]), int(pixel[2]), int(pixel[3])

    # 1. Beasthuman Taiga
    r_center, _, _, a_center = sample_splat(-2100.0, 1800.0)
    assert r_center > 200
    assert a_center == 0

    _, _, _, a_b = sample_splat(-930.36, 673.95)
    assert a_b == 0

    # 2. Demon Ashlands
    r_d_c, _, _, a_d_c = sample_splat(-2400.0, -1650.0)
    assert a_d_c > 200
    assert r_d_c == 0

    r_d, _, _, _ = sample_splat(-930.36, -677.95)
    assert r_d == 0

    # 3. Elf Sylvan Highlands
    _, g_e_c, _, a_e_c = sample_splat(2100.0, 600.0)
    assert g_e_c > 200
    assert a_e_c == 0

    # 4. Dragon Obsidian Alpine Peaks
    _, _, b_dr_c, a_dr_c = sample_splat(2200.0, -2100.0)
    assert b_dr_c > 200
    assert a_dr_c == 0


def test_radial_highways_and_road_mask() -> None:
    mask_path = Path("godot_client/assets/terrain/world_road_mask.png")
    assert mask_path.exists(), f"{mask_path} must exist"
    img = _load_png_grayscale(mask_path)
    assert img.shape == (1024, 1024), f"Expected (1024, 1024), got {img.shape}"

    def sample_mask(wx: float, wz: float) -> int:
        col = int(round(((wx + 4000.0) / 8000.0) * 1023.0))
        row = int(round(((wz + 4000.0) / 8000.0) * 1023.0))
        col = max(0, min(1023, col))
        row = max(0, min(1023, row))
        return int(img[row, col])

    highways = {
        "Aurelia Highway": (177.68, 545.85),
        "Sylvanor Highway": (575.0, -1.0),
        "Drakonis Spire Highway": (177.68, -547.85),
        "Fenris Hold Highway": (-465.18, 336.98),
        "Malakor Highway": (-465.18, -338.98),
    }
    for name, (wx, wz) in highways.items():
        val = sample_mask(wx, wz)
        assert val >= 128, f"{name} midpoint ({wx}, {wz}) road weight >= 128, got {val}"


def test_heightmap_bilinear_lookup() -> None:
    """Verifies O(1) elevation lookup, slope, and boundary protection on synthetic grid."""
    # Synthetic terrain: 128x128 grid with ramp from 0.0 to 100.0m
    data = np.linspace(0.0, 100.0, 128 * 128, dtype=np.float32).reshape(128, 128)

    hm = Heightmap(min_x=-1000.0, max_x=1000.0, min_z=-1000.0, max_z=1000.0)
    hm.data = data
    hm.rows = 128
    hm.cols = 128
    hm.scale_x = (128 - 1) / 2000.0
    hm.scale_z = (128 - 1) / 2000.0

    # Corners
    h_min = hm.get_elevation(-1000.0, -1000.0)
    assert h_min == pytest.approx(0.0, abs=1e-3)

    h_max = hm.get_elevation(1000.0, 1000.0)
    assert h_max == pytest.approx(100.0, abs=1e-3)

    # Center
    h_center = hm.get_elevation(0.0, 0.0)
    assert 40.0 < h_center < 60.0

    # Slope
    slope = hm.get_slope(0.0, 0.0, step=2.0)
    assert slope >= 0.0

    # Out of bounds clamping check (never crashes)
    h_oob = hm.get_elevation(-99999.0, 99999.0)
    assert isinstance(h_oob, float)

