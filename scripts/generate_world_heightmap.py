#!/usr/bin/env python3
"""
scripts/generate_world_heightmap.py
Generates a deterministic 5-biome heightmap and metadata for Gaia.
Produces:
1. data/world_heightmap.npy (512x512 float32 array for Python O(1) elevation lookups)
2. godot_client/assets/terrain/world_heightmap.png (16-bit grayscale PNG for Godot)
3. godot_client/assets/terrain/world_biome_splat.png (RGBA PNG for biome splatting)
4. godot_client/assets/terrain/terrain_metadata.json (Institutional pads and biome anchors)
"""

from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
TERRAIN_DIR = REPO_ROOT / "godot_client" / "assets" / "terrain"

# World Boundaries (10,000m x 10,000m)
WORLD_MIN_X = -5000.0
WORLD_MAX_X = 5000.0
WORLD_MIN_Z = -5000.0
WORLD_MAX_Z = 5000.0
RESOLUTION = 512
MAX_HEIGHT_METERS = 140.0


def _save_png_16bit_grayscale(filename: Path, array: np.ndarray):
    """Saves a 2D uint16 numpy array as a 16-bit grayscale PNG."""
    height, width = array.shape
    raw_data = bytearray()
    for row in array:
        raw_data.append(0)  # Filter type 0 (None)
        raw_data.extend(row.astype(">u2").tobytes())

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data))
        )

    header = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 16, 0, 0, 0, 0))
    idat = chunk(b"IDAT", zlib.compress(bytes(raw_data), level=6))
    iend = chunk(b"IEND", b"")

    with open(filename, "wb") as f:
        f.write(header + ihdr + idat + iend)


def _save_png_rgba(filename: Path, array: np.ndarray):
    """Saves a 3D (H, W, 4) uint8 numpy array as an 8-bit RGBA PNG."""
    height, width, _ = array.shape
    raw_data = bytearray()
    for row in array:
        raw_data.append(0)  # Filter type 0
        raw_data.extend(row.astype(np.uint8).tobytes())

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data))
        )

    header = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    idat = chunk(b"IDAT", zlib.compress(bytes(raw_data), level=6))
    iend = chunk(b"IEND", b"")

    with open(filename, "wb") as f:
        f.write(header + ihdr + idat + iend)


def generate_heightmap():
    print("=" * 70)
    print("GAIA DETERMINISTIC 5-BIOME HEIGHTMAP GENERATOR")
    print(f"World: {WORLD_MIN_X}..{WORLD_MAX_X}m x {WORLD_MIN_Z}..{WORLD_MAX_Z}m")
    print(f"Resolution: {RESOLUTION}x{RESOLUTION}")
    print("=" * 70)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TERRAIN_DIR.mkdir(parents=True, exist_ok=True)

    xs = np.linspace(WORLD_MIN_X, WORLD_MAX_X, RESOLUTION, dtype=np.float32)
    zs = np.linspace(WORLD_MIN_Z, WORLD_MAX_Z, RESOLUTION, dtype=np.float32)
    grid_x, grid_z = np.meshgrid(xs, zs)

    # 1. Base elevation: 18.0m floor
    elevation = np.full((RESOLUTION, RESOLUTION), 18.0, dtype=np.float32)

    # 2. Multi-octave natural terrain noise using deterministic harmonics
    def harmonic_noise(gx, gz, freq, amp, phase_x=0.0, phase_z=0.0):
        return amp * (
            np.sin(gx * freq + phase_x) * np.cos(gz * freq + phase_z)
            + 0.5 * np.cos((gx + gz) * freq * 0.7)
        )

    noise = (
        harmonic_noise(grid_x, grid_z, 0.0006, 12.0, 1.2, 0.5)
        + harmonic_noise(grid_x, grid_z, 0.0015, 6.0, 2.4, 1.8)
        + harmonic_noise(grid_x, grid_z, 0.0035, 2.5, 0.7, 3.1)
        + harmonic_noise(grid_x, grid_z, 0.0080, 1.0, 4.1, 2.2)
    )
    elevation += noise

    # 3. 5 Biome Topographic Features & Elevation Shaping
    # - Central Basin (Neutral Free City): (0, 0), smooth fertile river valley
    dist_center = np.sqrt(grid_x**2 + grid_z**2)
    center_weight = np.clip(1.0 - dist_center / 850.0, 0.0, 1.0)
    # Smooth central basin towards flat 18.0m
    elevation = elevation * (1.0 - center_weight * 0.85) + 18.0 * (center_weight * 0.85)

    # - Dragon Obsidian Peaks: (2500, -2500), North-East jagged mountains & caldera (70-120m)
    dist_dragon = np.sqrt((grid_x - 2500.0) ** 2 + (grid_z + 2500.0) ** 2)
    dragon_weight = np.clip(1.0 - dist_dragon / 2400.0, 0.0, 1.0)
    dragon_peaks = dragon_weight * (
        60.0
        + 25.0 * np.sin(grid_x * 0.002) ** 2
        + 20.0 * np.cos(grid_z * 0.002) ** 2
    )
    elevation += dragon_peaks

    # - Elf Emerald Highland Forest: (2200, 2000), South-East verdant plateaus (35-60m)
    dist_elf = np.sqrt((grid_x - 2200.0) ** 2 + (grid_z - 2000.0) ** 2)
    elf_weight = np.clip(1.0 - dist_elf / 2200.0, 0.0, 1.0)
    elf_plateaus = elf_weight * (
        25.0 + 8.0 * np.sin(grid_x * 0.001 + grid_z * 0.001)
    )
    elevation += elf_plateaus

    # - Human Temperate Plains: (-1800, 2000), South-West rolling fertile hills (20-35m)
    dist_human = np.sqrt((grid_x + 1800.0) ** 2 + (grid_z - 2000.0) ** 2)
    human_weight = np.clip(1.0 - dist_human / 2200.0, 0.0, 1.0)
    human_hills = human_weight * (6.0 + 4.0 * np.sin(grid_x * 0.0015))
    elevation += human_hills

    # - Beasthuman Northern Steppes/Taiga: (-2500, -2500), North-West rolling tundra/gorges (25-50m)
    dist_beast = np.sqrt((grid_x + 2500.0) ** 2 + (grid_z + 2500.0) ** 2)
    beast_weight = np.clip(1.0 - dist_beast / 2400.0, 0.0, 1.0)
    beast_gorges = beast_weight * (
        15.0 + 10.0 * np.cos(grid_x * 0.0015 + grid_z * 0.0015)
    )
    elevation += beast_gorges

    # - Demon Ashland Crags: (-3500, 500), West volcanic rift & sharp basalt crags (40-90m)
    dist_demon = np.sqrt((grid_x + 3500.0) ** 2 + (grid_z - 500.0) ** 2)
    demon_weight = np.clip(1.0 - dist_demon / 2200.0, 0.0, 1.0)
    demon_crags = demon_weight * (
        35.0
        + 18.0 * np.abs(np.sin(grid_x * 0.003))
        + 12.0 * np.abs(np.cos(grid_z * 0.0025))
    )
    elevation += demon_crags

    # 4. Flattened Institutional Landmark Pads (Neutral City at Basin)
    pads = {
        "world_library": {"x": 100.0, "z": 100.0, "radius": 70.0, "target_h": 18.0},
        "wtc_market": {"x": -100.0, "z": 100.0, "radius": 70.0, "target_h": 18.0},
        "courthouse": {"x": -100.0, "z": -100.0, "radius": 70.0, "target_h": 18.0},
        "cathedral_altar": {"x": 100.0, "z": -100.0, "radius": 70.0, "target_h": 18.0},
        "world_goddess_sanctum": {"x": 0.0, "z": 0.0, "radius": 85.0, "target_h": 18.5},
    }

    for _name, pad in pads.items():
        pad_dist = np.sqrt((grid_x - pad["x"]) ** 2 + (grid_z - pad["z"]) ** 2)
        inner_mask = pad_dist <= pad["radius"]
        falloff_mask = (pad_dist > pad["radius"]) & (pad_dist < pad["radius"] + 25.0)

        elevation[inner_mask] = pad["target_h"]
        blend = (pad_dist[falloff_mask] - pad["radius"]) / 25.0
        elevation[falloff_mask] = (
            pad["target_h"] * (1.0 - blend) + elevation[falloff_mask] * blend
        )

    # Clamp bounds: minimum elevation 5.0m, maximum 135.0m
    elevation = np.clip(elevation, 5.0, MAX_HEIGHT_METERS - 5.0).astype(np.float32)

    # 5. Save Python numpy elevation map
    npy_path = DATA_DIR / "world_heightmap.npy"
    np.save(npy_path, elevation)
    print(f"[+] Saved {npy_path} ({npy_path.stat().st_size / 1024:.1f} KB)")

    # 6. Save 16-bit Grayscale PNG for Godot
    normalized_16bit = np.clip(
        (elevation / MAX_HEIGHT_METERS) * 65535.0, 0, 65535
    ).astype(np.uint16)
    png_path = TERRAIN_DIR / "world_heightmap.png"
    _save_png_16bit_grayscale(png_path, normalized_16bit)
    print(f"[+] Saved {png_path} ({png_path.stat().st_size / 1024:.1f} KB)")

    # 7. Generate Biome Splat Map (RGBA)
    # R: Plains/Neutral, G: Forest, B: Dragon Obsidian, A: Demon Ashland / Steppes
    splat = np.zeros((RESOLUTION, RESOLUTION, 4), dtype=np.uint8)
    r_channel = np.clip(
        (human_weight + center_weight * 0.8) / 1.5 * 255.0, 0, 255
    ).astype(np.uint8)
    g_channel = np.clip(elf_weight * 255.0, 0, 255).astype(np.uint8)
    b_channel = np.clip(dragon_weight * 255.0, 0, 255).astype(np.uint8)
    a_channel = np.clip((demon_weight + beast_weight * 0.7) * 255.0, 0, 255).astype(
        np.uint8
    )

    splat[:, :, 0] = r_channel
    splat[:, :, 1] = g_channel
    splat[:, :, 2] = b_channel
    splat[:, :, 3] = a_channel

    splat_path = TERRAIN_DIR / "world_biome_splat.png"
    _save_png_rgba(splat_path, splat)
    print(f"[+] Saved {splat_path} ({splat_path.stat().st_size / 1024:.1f} KB)")

    # 8. Save Terrain Metadata JSON
    metadata = {
        "version": "3.0.0",
        "world_bounds": {
            "min_x": WORLD_MIN_X,
            "max_x": WORLD_MAX_X,
            "min_z": WORLD_MIN_Z,
            "max_z": WORLD_MAX_Z,
        },
        "resolution": RESOLUTION,
        "max_height_meters": MAX_HEIGHT_METERS,
        "landmark_pads": pads,
        "biomes": {
            "central_basin": {"center_x": 0.0, "center_z": 0.0, "radius": 850.0},
            "human_plains": {"center_x": -1800.0, "center_z": 2000.0, "radius": 2200.0},
            "elf_highlands": {"center_x": 2200.0, "center_z": 2000.0, "radius": 2200.0},
            "dragon_peaks": {"center_x": 2500.0, "center_z": -2500.0, "radius": 2400.0},
            "beasthuman_taiga": {"center_x": -2500.0, "center_z": -2500.0, "radius": 2400.0},
            "demon_crags": {"center_x": -3500.0, "center_z": 500.0, "radius": 2200.0},
        },
    }
    meta_path = TERRAIN_DIR / "terrain_metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"[+] Saved {meta_path}")

    # Summary Statistics
    print("\nElevation Stats:")
    print(f"  Min Elevation: {elevation.min():.2f}m")
    print(f"  Max Elevation: {elevation.max():.2f}m")
    print(f"  Mean Elevation: {elevation.mean():.2f}m")
    print(f"  Center (0, 0) Elevation: {elevation[RESOLUTION//2, RESOLUTION//2]:.2f}m")
    print("=" * 70)


if __name__ == "__main__":
    generate_heightmap()
