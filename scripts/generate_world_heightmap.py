#!/usr/bin/env python3
"""
scripts/generate_world_heightmap.py
Generates a deterministic 1024x1024 8km x 8km (-4000..4000m) 5-biome concentric open-world
heightmap, imperial road network, river systems, ocean shelf, and road mask for Gaia.

Outputs:
1. data/world_heightmap.npy (1024x1024 float32 elevation array for Python O(1) lookups)
2. godot_client/assets/terrain/world_heightmap.bin (1024x1024 raw float32 bytes for Godot)
3. godot_client/assets/terrain/world_heightmap.png (16-bit grayscale PNG preview)
4. godot_client/assets/terrain/world_biome_splat.png (RGBA PNG for multi-surface biome blending)
5. godot_client/assets/terrain/world_road_mask.png (8-bit grayscale PNG for paved roads/plazas)
6. godot_client/assets/terrain/terrain_metadata.json (Institutional pads, cities, roads, and bounds)
7. godot_client/assets/terrain/world_roads.json (Imperial Highway waypoints and specifications)
"""

from __future__ import annotations

import json
import math
import struct
import zlib
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
TERRAIN_DIR = REPO_ROOT / "godot_client" / "assets" / "terrain"

# World Geometry Specifications (8,000m x 8,000m)
WORLD_MIN_X = -4000.0
WORLD_MAX_X = 4000.0
WORLD_MIN_Z = -4000.0
WORLD_MAX_Z = 4000.0
RESOLUTION = 1024
SEA_LEVEL = 0.0
MIN_HEIGHT_METERS = -25.0
MAX_HEIGHT_METERS = 180.0

# Ring 1 City Specifications (r = 1,150m, 72° spacing)
# Angles: 0°, 72°, 144°, 216°, 288°
RING_1_CITIES = {
    "sylvanor": {
        "name": "Sylvanor",
        "race": "ELF",
        "angle_deg": 0.0,
        "x": 1150.0,
        "z": 0.0,
        "target_h": 28.0,
        "radius": 280.0,
        "blend_radius": 380.0,
        "description": "Elf emerald highland forest",
    },
    "aurelia": {
        "name": "Aurelia",
        "race": "HUMAN",
        "angle_deg": 72.0,
        "x": round(1150.0 * math.cos(math.radians(72.0)), 2),
        "z": round(1150.0 * math.sin(math.radians(72.0)), 2),
        "target_h": 18.0,
        "radius": 280.0,
        "blend_radius": 380.0,
        "description": "Human sunlit temperate plains with southern bay access",
    },
    "fenris_hold": {
        "name": "Fenris Hold",
        "race": "BEASTHUMAN",
        "angle_deg": 144.0,
        "x": round(1150.0 * math.cos(math.radians(144.0)), 2),
        "z": round(1150.0 * math.sin(math.radians(144.0)), 2),
        "target_h": 24.0,
        "radius": 280.0,
        "blend_radius": 380.0,
        "description": "Beasthuman rugged timber steppes and taiga",
    },
    "malakor": {
        "name": "Malakor",
        "race": "DEMON",
        "angle_deg": 216.0,
        "x": round(1150.0 * math.cos(math.radians(216.0)), 2),
        "z": round(1150.0 * math.sin(math.radians(216.0)), 2),
        "target_h": 42.0,
        "radius": 280.0,
        "blend_radius": 380.0,
        "description": "Demon basalt crags and volcanic ashlands",
    },
    "drakonis_spire": {
        "name": "Drakonis Spire",
        "race": "DRAGON",
        "angle_deg": 288.0,
        "x": round(1150.0 * math.cos(math.radians(288.0)), 2),
        "z": round(1150.0 * math.sin(math.radians(288.0)), 2),
        "target_h": 68.0,
        "radius": 280.0,
        "blend_radius": 380.0,
        "description": "Dragon obsidian alpine peaks and volcanic ridges",
    },
}

# Ring 0 Institutional Pads
RING_0_PADS = {
    "world_goddess_palace": {"x": 0.0, "z": 0.0, "radius": 95.0, "target_h": 32.0},
    "world_library": {"x": 180.0, "z": 180.0, "radius": 55.0, "target_h": 24.0},
    "wtc_market": {"x": -180.0, "z": 180.0, "radius": 55.0, "target_h": 24.0},
    "courthouse": {"x": -180.0, "z": -180.0, "radius": 55.0, "target_h": 24.0},
    "cathedral_altar": {"x": 180.0, "z": -180.0, "radius": 55.0, "target_h": 24.0},
}


def _save_png_16bit_grayscale(filename: Path, array: np.ndarray) -> None:
    """Saves a 2D uint16 numpy array as a 16-bit grayscale PNG."""
    height, width = array.shape
    raw_data = bytearray()
    for row in array:
        raw_data.append(0)  # Filter type 0
        raw_data.extend(row.astype(">u2").tobytes())

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    header = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 16, 0, 0, 0, 0))
    idat = chunk(b"IDAT", zlib.compress(bytes(raw_data), level=6))
    iend = chunk(b"IEND", b"")

    with open(filename, "wb") as f:
        f.write(header + ihdr + idat + iend)


def _save_png_8bit_grayscale(filename: Path, array: np.ndarray) -> None:
    """Saves a 2D uint8 numpy array as an 8-bit grayscale PNG."""
    height, width = array.shape
    raw_data = bytearray()
    for row in array:
        raw_data.append(0)  # Filter type 0
        raw_data.extend(row.astype(np.uint8).tobytes())

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    header = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
    idat = chunk(b"IDAT", zlib.compress(bytes(raw_data), level=6))
    iend = chunk(b"IEND", b"")

    with open(filename, "wb") as f:
        f.write(header + ihdr + idat + iend)


def _save_png_rgba(filename: Path, array: np.ndarray) -> None:
    """Saves a 3D (H, W, 4) uint8 numpy array as an 8-bit RGBA PNG."""
    height, width, _ = array.shape
    raw_data = bytearray()
    for row in array:
        raw_data.append(0)  # Filter type 0
        raw_data.extend(row.astype(np.uint8).tobytes())

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    header = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    idat = chunk(b"IDAT", zlib.compress(bytes(raw_data), level=6))
    iend = chunk(b"IEND", b"")

    with open(filename, "wb") as f:
        f.write(header + ihdr + idat + iend)


def dist_to_segment(
    gx: np.ndarray, gz: np.ndarray, ax: float, az: float, bx: float, bz: float
) -> tuple[np.ndarray, np.ndarray]:
    """Computes minimum distance and parametric t (0..1) from 2D grid to segment AB."""
    vx = bx - ax
    vz = bz - az
    len_sq = vx * vx + vz * vz
    if len_sq == 0.0:
        d = np.sqrt((gx - ax) ** 2 + (gz - az) ** 2)
        return d, np.zeros_like(d)

    u = ((gx - ax) * vx + (gz - az) * vz) / len_sq
    u = np.clip(u, 0.0, 1.0)
    closest_x = ax + u * vx
    closest_z = az + u * vz
    dist = np.sqrt((gx - closest_x) ** 2 + (gz - closest_z) ** 2)
    return dist, u


def generate_heightmap() -> None:
    print("=" * 80)
    print("GAIA DETERMINISTIC 8km x 8km (1024x1024) CONCENTRIC OPEN-WORLD GENERATOR")
    print(f"World: {WORLD_MIN_X}..{WORLD_MAX_X}m x {WORLD_MIN_Z}..{WORLD_MAX_Z}m")
    print(f"Resolution: {RESOLUTION}x{RESOLUTION} | Sea Level: {SEA_LEVEL}m")
    print("=" * 80)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TERRAIN_DIR.mkdir(parents=True, exist_ok=True)

    xs = np.linspace(WORLD_MIN_X, WORLD_MAX_X, RESOLUTION, dtype=np.float32)
    zs = np.linspace(WORLD_MIN_Z, WORLD_MAX_Z, RESOLUTION, dtype=np.float32)
    grid_x, grid_z = np.meshgrid(xs, zs)
    dist_origin = np.sqrt(grid_x**2 + grid_z**2)

    # 1. Base Elevation Floor: 16.0m
    elevation = np.full((RESOLUTION, RESOLUTION), 16.0, dtype=np.float32)

    # 2. Multi-Octave Deterministic Harmonic Terrain Noise
    def harmonic_noise(gx, gz, freq, amp, phase_x=0.0, phase_z=0.0):
        return amp * (
            np.sin(gx * freq + phase_x) * np.cos(gz * freq + phase_z)
            + 0.5 * np.cos((gx + gz) * freq * 0.7)
        )

    noise = (
        harmonic_noise(grid_x, grid_z, 0.0004, 14.0, 1.2, 0.5)
        + harmonic_noise(grid_x, grid_z, 0.0010, 7.5, 2.4, 1.8)
        + harmonic_noise(grid_x, grid_z, 0.0025, 3.5, 0.7, 3.1)
        + harmonic_noise(grid_x, grid_z, 0.0060, 1.5, 4.1, 2.2)
    )
    elevation += noise

    # 3. Macro Biome Mountain Ranges & Wilderness Basins (Ring 2)
    # - Dragon Obsidian Alpine Peaks (North-East, centered around 2100, -2200)
    d_dragon = np.sqrt((grid_x - 2100.0) ** 2 + (grid_z + 2200.0) ** 2)
    w_dragon = np.clip(1.0 - d_dragon / 1900.0, 0.0, 1.0)
    dragon_ridges = w_dragon * (
        75.0
        + 45.0 * np.sin(grid_x * 0.0025 + 0.8) ** 2
        + 35.0 * np.cos(grid_z * 0.0022 - 0.4) ** 2
        + 15.0 * np.sin((grid_x + grid_z) * 0.003) ** 2
    )
    elevation += dragon_ridges

    # - Demon Volcanic Caldera & Ashland Crags (North-West, centered at -2400, -1650)
    d_demon = np.sqrt((grid_x + 2400.0) ** 2 + (grid_z + 1650.0) ** 2)
    w_demon = np.clip(1.0 - d_demon / 1800.0, 0.0, 1.0)
    # Volcanic cone rising to ~145m with a caldera depression crater at the summit (r < 180m)
    cone_height = w_demon * (
        85.0 + 30.0 * np.abs(np.sin(grid_x * 0.0035)) + 25.0 * np.abs(np.cos(grid_z * 0.0030))
    )
    # Subtle caldera depression at summit
    caldera_depression = np.clip(1.0 - d_demon / 220.0, 0.0, 1.0) * 16.0
    elevation += cone_height - caldera_depression

    # - Elf Emerald Highlands (East, centered at 2100, 600)
    d_elf = np.sqrt((grid_x - 2100.0) ** 2 + (grid_z - 600.0) ** 2)
    w_elf = np.clip(1.0 - d_elf / 1700.0, 0.0, 1.0)
    elf_highlands = w_elf * (
        24.0 + 12.0 * np.sin(grid_x * 0.0018 + grid_z * 0.0012) + 8.0 * np.cos(grid_z * 0.002)
    )
    elevation += elf_highlands

    # - Human Fertile Plains & Bay (South-East, centered at 1200, 2000)
    d_human = np.sqrt((grid_x - 1200.0) ** 2 + (grid_z - 2000.0) ** 2)
    w_human = np.clip(1.0 - d_human / 1800.0, 0.0, 1.0)
    human_plains = w_human * (6.0 + 4.0 * np.sin(grid_x * 0.0015))
    elevation += human_plains

    # - Beasthuman Rugged Taiga & Steppes (South-West, centered at -2100, 1800)
    d_beast = np.sqrt((grid_x + 2100.0) ** 2 + (grid_z - 1800.0) ** 2)
    w_beast = np.clip(1.0 - d_beast / 1800.0, 0.0, 1.0)
    beast_steppes = w_beast * (18.0 + 8.0 * np.cos(grid_x * 0.002 + grid_z * 0.002))
    elevation += beast_steppes

    # 4. Ring 1 — 5 Leveled Racial Cities (r = 1,150m, radius 280m flat)
    for _key, city in RING_1_CITIES.items():
        cx, cz = city["x"], city["z"]
        target_h = city["target_h"]
        r_flat = city["radius"]  # 280.0
        r_blend = city["blend_radius"]  # 380.0

        d_city = np.sqrt((grid_x - cx) ** 2 + (grid_z - cz) ** 2)
        flat_mask = d_city <= r_flat
        blend_mask = (d_city > r_flat) & (d_city < r_blend)

        elevation[flat_mask] = target_h
        t = (d_city[blend_mask] - r_flat) / (r_blend - r_flat)
        # Smoothstep Hermite blend
        smooth_t = t * t * (3.0 - 2.0 * t)
        elevation[blend_mask] = target_h * (1.0 - smooth_t) + elevation[blend_mask] * smooth_t

    # 5. Imperial Road Network (5 Radial Highways + Circular Ring Road)
    # Prepare Road Mask (0..255)
    road_mask = np.zeros((RESOLUTION, RESOLUTION), dtype=np.float32)

    # 5a. Circular Ring Road at r = 1,150m (width 10m)
    d_ring = np.abs(dist_origin - 1150.0)
    # Angular coordinate for smooth highway grading between city elevations
    angles = np.arctan2(grid_z, grid_x)  # -pi .. pi
    # Normalize angles to [0, 2pi)
    angles_pos = np.mod(angles, 2.0 * np.pi)
    city_angles_rad = [math.radians(c["angle_deg"]) for c in RING_1_CITIES.values()]
    city_heights = [c["target_h"] for c in RING_1_CITIES.values()]
    # Append wrap-around for 0°/360°
    city_angles_rad.append(2.0 * math.pi)
    city_heights.append(city_heights[0])

    ring_interp_h = np.interp(angles_pos, city_angles_rad, city_heights).astype(np.float32)

    ring_road_zone = d_ring <= 14.0
    ring_inner_road = d_ring <= 5.0
    # Blend ring road into terrain
    t_ring = np.clip((d_ring[ring_road_zone] - 5.0) / 9.0, 0.0, 1.0)
    smooth_t_ring = t_ring * t_ring * (3.0 - 2.0 * t_ring)
    elevation[ring_road_zone] = (
        ring_interp_h[ring_road_zone] * (1.0 - smooth_t_ring)
        + elevation[ring_road_zone] * smooth_t_ring
    )
    road_mask[ring_inner_road] = 1.0
    road_mask[ring_road_zone] = np.maximum(road_mask[ring_road_zone], 1.0 - smooth_t_ring)

    # 5b. 5 Radial Highways (Acropolis r=360m to City Gate r=900m)
    road_waypoints: list[dict] = []
    for _key, city in RING_1_CITIES.items():
        cx, cz = city["x"], city["z"]
        target_h = city["target_h"]
        # Start at Acropolis plaza boundary (r = 360m)
        angle_rad = math.atan2(cz, cx)
        ax = 360.0 * math.cos(angle_rad)
        az = 360.0 * math.sin(angle_rad)
        # End at city boundary (r = 900m)
        bx = 900.0 * math.cos(angle_rad)
        bz = 900.0 * math.sin(angle_rad)

        dist_road, param_t = dist_to_segment(grid_x, grid_z, ax, az, bx, bz)
        # Grade highway smoothly from Acropolis plaza (24.0m) to city elevation
        road_h = 24.0 * (1.0 - param_t) + target_h * param_t

        radial_zone = dist_road <= 12.0
        t_rad = np.clip((dist_road[radial_zone] - 5.0) / 7.0, 0.0, 1.0)
        smooth_t_rad = t_rad * t_rad * (3.0 - 2.0 * t_rad)
        elevation[radial_zone] = (
            road_h[radial_zone] * (1.0 - smooth_t_rad) + elevation[radial_zone] * smooth_t_rad
        )
        road_mask[radial_zone] = np.maximum(road_mask[radial_zone], 1.0 - smooth_t_rad)

        road_waypoints.append(
            {
                "name": f"Imperial_Highway_{city['name']}",
                "city": city["name"],
                "start": {"x": round(ax, 1), "y": 24.0, "z": round(az, 1)},
                "end": {"x": round(bx, 1), "y": target_h, "z": round(bz, 1)},
                "width": 10.0,
            }
        )

    # 6. Ring 0 — Imperial Acropolis at (0, 0)
    # - Palace Plateau (r <= 95m): flat at 32.0m
    # - Step Down (95m < r <= 160m): gentle slope from 32.0m to 24.0m
    # - Level Outer Institutional Plaza (160m < r <= 360m): flat at 24.0m
    # - Plaza Falloff (360m < r <= 520m): gentle slope from 24.0m to surrounding terrain
    r0_core = dist_origin <= 95.0
    r0_step = (dist_origin > 95.0) & (dist_origin <= 160.0)
    r0_plaza = (dist_origin > 160.0) & (dist_origin <= 360.0)
    r0_falloff = (dist_origin > 360.0) & (dist_origin <= 520.0)

    elevation[r0_core] = 32.0
    t_step = (dist_origin[r0_step] - 95.0) / 65.0
    smooth_step = t_step * t_step * (3.0 - 2.0 * t_step)
    elevation[r0_step] = 32.0 * (1.0 - smooth_step) + 24.0 * smooth_step

    elevation[r0_plaza] = 24.0

    t_falloff = (dist_origin[r0_falloff] - 360.0) / 160.0
    smooth_falloff = t_falloff * t_falloff * (3.0 - 2.0 * t_falloff)
    elevation[r0_falloff] = 24.0 * (1.0 - smooth_falloff) + elevation[r0_falloff] * smooth_falloff

    # Mark Acropolis core and plaza on road mask
    road_mask[dist_origin <= 360.0] = 1.0
    road_mask[r0_falloff] = np.maximum(road_mask[r0_falloff], 1.0 - smooth_falloff)

    # Re-enforce the 4 Institutional Pads in outer plaza (y = 24.0m)
    for _key, pad in RING_0_PADS.items():
        px, pz = pad["x"], pad["z"]
        pad_dist = np.sqrt((grid_x - px) ** 2 + (grid_z - pz) ** 2)
        pad_inner = pad_dist <= pad["radius"]
        elevation[pad_inner] = pad["target_h"]
        road_mask[pad_inner] = 1.0

    # 7. Carve Natural Rivers (Ring 2)
    # 3 Rivers flowing down to ocean with riverbed y < 0.0m
    rivers = [
        {
            "name": "Drakonis_Run",
            "waypoints": [
                (700.0, -1500.0),
                (1400.0, -2100.0),
                (2100.0, -2650.0),
                (2700.0, -3150.0),
                (3200.0, -3500.0),
            ],
            "bed_depth": -2.5,
            "width": 30.0,
            "bank_width": 55.0,
        },
        {
            "name": "Sylvan_Brook",
            "waypoints": [
                (1600.0, 300.0),
                (2200.0, 500.0),
                (2750.0, 750.0),
                (3250.0, 950.0),
                (3650.0, 1100.0),
            ],
            "bed_depth": -2.0,
            "width": 26.0,
            "bank_width": 50.0,
        },
        {
            "name": "Aurelian_River",
            "waypoints": [
                (200.0, 1400.0),
                (350.0, 2100.0),
                (450.0, 2700.0),
                (550.0, 3200.0),
                (650.0, 3600.0),
            ],
            "bed_depth": -2.2,
            "width": 28.0,
            "bank_width": 52.0,
        },
    ]

    for river in rivers:
        pts = river["waypoints"]
        bed_d = river["bed_depth"]
        rw = river["width"]
        rb = river["bank_width"]

        # Calculate minimum distance to piecewise linear segments
        min_dist_to_river = np.full((RESOLUTION, RESOLUTION), 99999.0, dtype=np.float32)
        for i in range(len(pts) - 1):
            ax, az = pts[i]
            bx, bz = pts[i + 1]
            d_seg, _ = dist_to_segment(grid_x, grid_z, ax, az, bx, bz)
            min_dist_to_river = np.minimum(min_dist_to_river, d_seg)

        river_bed = min_dist_to_river <= rw * 0.5
        river_bank = (min_dist_to_river > rw * 0.5) & (min_dist_to_river <= rb)

        elevation[river_bed] = bed_d
        t_bank = (min_dist_to_river[river_bank] - (rw * 0.5)) / (rb - (rw * 0.5))
        smooth_bank = t_bank * t_bank * (3.0 - 2.0 * t_bank)
        elevation[river_bank] = bed_d * (1.0 - smooth_bank) + elevation[river_bank] * smooth_bank
        # Exclude roads from riverbed
        road_mask[river_bed] = 0.0

    # 8. Ring 3 — Great Ocean, Beaches & Deep Ocean Floor (r > 3,300m)
    # Coastal slope: r = 3,300m .. 3,500m drops through beach (4.5m .. 0.0m) to ocean
    # Submerged shelf: r = 3,500m .. 3,750m drops to -25.0m
    # Deep ocean: r >= 3,750m flat at -25.0m
    ocean_shelf = (dist_origin > 3300.0) & (dist_origin <= 3750.0)
    deep_ocean = dist_origin > 3750.0

    t_ocean = (dist_origin[ocean_shelf] - 3300.0) / 450.0
    smooth_ocean = t_ocean * t_ocean * (3.0 - 2.0 * t_ocean)
    elevation[ocean_shelf] = (
        elevation[ocean_shelf] * (1.0 - smooth_ocean) + MIN_HEIGHT_METERS * smooth_ocean
    )
    elevation[deep_ocean] = MIN_HEIGHT_METERS

    # 4 Scenic Outer Islets (r > 3450m)
    outer_islets = [
        {"name": "Sunken_Isle", "x": -2900.0, "z": 2500.0, "radius": 220.0, "peak_h": 14.0},
        {"name": "Coral_Atoll", "x": 2500.0, "z": 2700.0, "radius": 200.0, "peak_h": 12.0},
        {"name": "Northwatch_Isle", "x": 0.0, "z": -3600.0, "radius": 250.0, "peak_h": 18.0},
        {"name": "Mist_Isle", "x": -2800.0, "z": -2600.0, "radius": 200.0, "peak_h": 15.0},
    ]

    for islet in outer_islets:
        d_isle = np.sqrt((grid_x - islet["x"]) ** 2 + (grid_z - islet["z"]) ** 2)
        r_isle = islet["radius"]
        mask_isle = d_isle <= r_isle
        t_isle = d_isle[mask_isle] / r_isle
        isle_profile = (1.0 - t_isle**2) * (islet["peak_h"] - MIN_HEIGHT_METERS) + MIN_HEIGHT_METERS
        elevation[mask_isle] = np.maximum(elevation[mask_isle], isle_profile)

    # Final safety clamp
    elevation = np.clip(elevation, MIN_HEIGHT_METERS, MAX_HEIGHT_METERS).astype(np.float32)

    # 9. Save Python numpy elevation map
    npy_path = DATA_DIR / "world_heightmap.npy"
    np.save(npy_path, elevation)
    print(f"[+] Saved {npy_path} ({npy_path.stat().st_size / 1024:.1f} KB)")

    # 10. Save Godot binary float32 elevation array
    bin_path = TERRAIN_DIR / "world_heightmap.bin"
    with open(bin_path, "wb") as f:
        f.write(elevation.tobytes())
    print(f"[+] Saved {bin_path} ({bin_path.stat().st_size / 1024:.1f} KB)")

    # 11. Save 16-bit Grayscale PNG preview for Godot
    # Map range [-25.0 .. 180.0] into [0 .. 65535]
    height_range = MAX_HEIGHT_METERS - MIN_HEIGHT_METERS
    norm_16 = np.clip(((elevation - MIN_HEIGHT_METERS) / height_range) * 65535.0, 0, 65535).astype(
        np.uint16
    )
    png_path = TERRAIN_DIR / "world_heightmap.png"
    _save_png_16bit_grayscale(png_path, norm_16)
    print(f"[+] Saved {png_path} ({png_path.stat().st_size / 1024:.1f} KB)")

    # 12. Save Road Mask PNG (8-bit grayscale)
    road_mask_u8 = np.clip(road_mask * 255.0, 0, 255).astype(np.uint8)
    road_mask_path = TERRAIN_DIR / "world_road_mask.png"
    _save_png_8bit_grayscale(road_mask_path, road_mask_u8)
    print(f"[+] Saved {road_mask_path} ({road_mask_path.stat().st_size / 1024:.1f} KB)")

    # 13. Save Biome Splat Map (RGBA)
    # R: Plains/Neutral/Roads, G: Forest/Elf Highlands, B: Dragon Obsidian, A: Demon Ashland
    splat = np.zeros((RESOLUTION, RESOLUTION, 4), dtype=np.uint8)
    # Normalize weights
    r_chan = np.clip((w_human + (dist_origin < 1200.0) * 0.7 + road_mask) * 255.0, 0, 255)
    g_chan = np.clip(w_elf * 255.0, 0, 255)
    b_chan = np.clip(w_dragon * 255.0, 0, 255)
    a_chan = np.clip((w_demon + w_beast * 0.7) * 255.0, 0, 255)

    splat[:, :, 0] = r_chan.astype(np.uint8)
    splat[:, :, 1] = g_chan.astype(np.uint8)
    splat[:, :, 2] = b_chan.astype(np.uint8)
    splat[:, :, 3] = a_chan.astype(np.uint8)

    splat_path = TERRAIN_DIR / "world_biome_splat.png"
    _save_png_rgba(splat_path, splat)
    print(f"[+] Saved {splat_path} ({splat_path.stat().st_size / 1024:.1f} KB)")

    # 14. Save Roads JSON
    roads_metadata = {
        "ring_road": {
            "radius": 1150.0,
            "width": 10.0,
            "connected_cities": list(RING_1_CITIES.keys()),
        },
        "radial_highways": road_waypoints,
    }
    roads_path = TERRAIN_DIR / "world_roads.json"
    with open(roads_path, "w", encoding="utf-8") as f:
        json.dump(roads_metadata, f, indent=2)
    print(f"[+] Saved {roads_path}")

    # 15. Save Terrain Metadata JSON
    metadata = {
        "version": "4.0.0",
        "world_bounds": {
            "min_x": WORLD_MIN_X,
            "max_x": WORLD_MAX_X,
            "min_z": WORLD_MIN_Z,
            "max_z": WORLD_MAX_Z,
        },
        "resolution": RESOLUTION,
        "sea_level": SEA_LEVEL,
        "min_height_meters": MIN_HEIGHT_METERS,
        "max_height_meters": MAX_HEIGHT_METERS,
        "ring_0_acropolis": {
            "center": {"x": 0.0, "z": 0.0},
            "palace_plateau": {"radius": 95.0, "target_h": 32.0},
            "outer_plaza": {"min_radius": 160.0, "max_radius": 360.0, "target_h": 24.0},
            "pads": RING_0_PADS,
        },
        "ring_1_cities": RING_1_CITIES,
        "ring_2_wilderness": {
            "min_radius": 1500.0,
            "max_radius": 3300.0,
            "demon_caldera_peak": {"x": -2400.0, "z": -1650.0, "target_h": 145.0},
            "dragon_peaks_ridge": {"x": 2100.0, "z": -2200.0, "target_h": 165.0},
            "rivers": [r["name"] for r in rivers],
        },
        "ring_3_ocean": {
            "beach_elevation_range": [0.0, 4.5],
            "deep_ocean_floor": -25.0,
            "ocean_radius_start": 3300.0,
            "islets": outer_islets,
        },
    }
    meta_path = TERRAIN_DIR / "terrain_metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"[+] Saved {meta_path}")

    # 16. Verification Summary
    print("\nElevation Quality Stats:")
    print(f"  Min Elevation: {elevation.min():.2f}m (Deep Ocean Floor)")
    print(f"  Max Elevation: {elevation.max():.2f}m (Dragon Alpine Peaks)")
    acropolis_elev = elevation[RESOLUTION // 2, RESOLUTION // 2]
    print(f"  Acropolis Core (0, 0): {acropolis_elev:.2f}m (Expected 32.0m)")
    for _ckey, city in RING_1_CITIES.items():
        col = int((city["x"] - WORLD_MIN_X) / (WORLD_MAX_X - WORLD_MIN_X) * (RESOLUTION - 1))
        row = int((city["z"] - WORLD_MIN_Z) / (WORLD_MAX_Z - WORLD_MIN_Z) * (RESOLUTION - 1))
        actual_h = elevation[row, col]
        print(
            f"  City {city['name']} ({city['x']}, {city['z']}): {actual_h:.2f}m "
            f"(Target: {city['target_h']}m)"
        )
    print("=" * 80)


if __name__ == "__main__":
    generate_heightmap()
