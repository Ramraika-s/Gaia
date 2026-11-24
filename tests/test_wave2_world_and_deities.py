"""
tests/test_wave2_world_and_deities.py
Verification suite for Gaia v4.0 Remediation Wave 2:
- Biome splat channel normalization and separation (zero Demon bleed into Beasthuman Taiga).
- DivineAutonomyEngine:
  - 5-Sister Council non-overlapping 72° distribution around Courtyard dais.
  - Ground elevation without dais offset when outside 8m of home / dais.
  - Synchronization of bestowed deity names into DEITY_SYNC records.
  - Correct Godot-aligned facing yaw.
"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import numpy as np

from sim_core.divine.autonomy import (
    DEITY_COUNCIL_ORDER,
    PALACE_COURTYARD_DAIS,
    DivineAutonomyEngine,
)
from sim_core.schemas import DeitySlot, Vec3


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


def test_biome_splat_channel_normalization_and_separation() -> None:
    splat_path = Path("godot_client/assets/terrain/world_biome_splat.png")
    assert splat_path.exists(), "godot_client/assets/terrain/world_biome_splat.png must exist"

    img = _load_png_rgba(splat_path)
    assert img.shape == (1024, 1024, 4), f"Expected (1024, 1024, 4), got {img.shape}"

    # Helper to sample RGBA at world (x, z) coords
    def sample_splat(wx: float, wz: float) -> tuple[int, int, int, int]:
        col = int(round(((wx + 4000.0) / 8000.0) * 1023.0))
        row = int(round(((wz + 4000.0) / 8000.0) * 1023.0))
        col = max(0, min(1023, col))
        row = max(0, min(1023, row))
        pixel = img[row, col]
        return int(pixel[0]), int(pixel[1]), int(pixel[2]), int(pixel[3])

    # 1. Beasthuman Taiga
    # Biome center: (-2100.0, 1800.0), City: Fenris Hold (-930.36, 673.95)
    r_center, g_center, b_center, a_center = sample_splat(-2100.0, 1800.0)
    assert r_center > 200, f"Beasthuman Taiga center must have maximum R, got {r_center}"
    assert a_center == 0, (
        f"Beasthuman Taiga center must have ZERO Demon Ashlands (A), got {a_center}"
    )

    # Fenris Hold (x=-930.36, z=673.95) must have ZERO Demon Ashlands bleed (A == 0)
    _r_b, _g_b, _b_b, a_b = sample_splat(-930.36, 673.95)
    assert a_b == 0, f"Fenris Hold must have ZERO Demon Ashlands bleed (A), got {a_b}"

    # 2. Demon Ashlands
    # Biome center: (-2400.0, -1650.0), City: Malakor (-930.36, -677.95)
    r_d_c, g_d_c, b_d_c, a_d_c = sample_splat(-2400.0, -1650.0)
    assert a_d_c > 200, f"Demon caldera center must have maximum A, got {a_d_c}"
    assert r_d_c == 0, f"Demon caldera center must have ZERO Beasthuman Taiga (R), got {r_d_c}"

    # Malakor must have ZERO Beasthuman Taiga bleed (R == 0)
    r_d, _g_d, _b_d, _a_d = sample_splat(-930.36, -677.95)
    assert r_d == 0, f"Malakor must have ZERO Beasthuman Taiga bleed (R), got {r_d}"

    # 3. Elf Sylvan Highlands
    # Biome center: (2100.0, 600.0), City: Sylvanor (1150.0, -2.0)
    r_e_c, g_e_c, b_e_c, a_e_c = sample_splat(2100.0, 600.0)
    assert g_e_c > 200, f"Elf highlands center must have maximum G, got {g_e_c}"
    assert a_e_c == 0, f"Elf highlands center must have ZERO Demon Ashlands (A), got {a_e_c}"

    # 4. Dragon Obsidian Alpine Peaks
    # Biome center: (2200.0, -2100.0), City: Drakonis Spire (355.37, -1095.71)
    r_dr_c, g_dr_c, b_dr_c, a_dr_c = sample_splat(2200.0, -2100.0)
    assert b_dr_c > 200, f"Dragon peaks center must have maximum B, got {b_dr_c}"
    assert a_dr_c == 0, f"Dragon peaks center must have ZERO Demon Ashlands (A), got {a_dr_c}"


def test_divine_autonomy_convene_council_non_overlapping() -> None:
    autonomy = DivineAutonomyEngine(engine=None)
    msg = autonomy.issue_god_order("CONVENE_COUNCIL")
    assert "Convened" in msg

    # World Goddess should target courtyard center
    goddess = autonomy.deities["world_goddess"]
    assert goddess.current_order == "CONVENE_COUNCIL"
    assert goddess.target_pos is not None
    assert goddess.target_pos.x == PALACE_COURTYARD_DAIS.x
    assert goddess.target_pos.z == PALACE_COURTYARD_DAIS.z

    # Check 5 God-Mothers positions are distinct with 72° spacing at r = 8.0m
    council_positions: list[Vec3] = []
    for slot in DEITY_COUNCIL_ORDER:
        deity = autonomy.deities[slot]
        assert deity.current_order == "CONVENE_COUNCIL"
        assert deity.target_pos is not None
        council_positions.append(deity.target_pos)

    assert len(council_positions) == 5
    for i in range(len(council_positions)):
        for j in range(i + 1, len(council_positions)):
            p1 = council_positions[i]
            p2 = council_positions[j]
            dist = math.hypot(p1.x - p2.x, p1.z - p2.z)
            # With r=8.0 and 72° angle, chord distance is 2 * 8 * sin(36°) = 9.40m
            assert dist >= 8.5, (
                f"Deities {DEITY_COUNCIL_ORDER[i]} and {DEITY_COUNCIL_ORDER[j]} "
                f"are too close: {dist:.2f}m (must be distinct >= 8.5m)"
            )


def test_divine_autonomy_grounding_off_dais() -> None:
    mock_engine = MagicMock()
    mock_heightmap = MagicMock()
    # Mock elevation returns constant 20.0
    mock_heightmap.get_elevation.return_value = 20.0
    mock_engine.heightmap = mock_heightmap
    mock_engine.divine_hierarchy = MagicMock()
    mock_engine.divine_hierarchy.entities = {}

    autonomy = DivineAutonomyEngine(engine=mock_engine)
    human_gm = autonomy.deities["gm_human"]
    assert human_gm.dais_offset == 3.2

    # Place deity far away from home (home is at x=355.37, z=1091.71)
    human_gm.pos = Vec3(x=0.0, y=0.0, z=200.0)
    human_gm.target_pos = Vec3(x=0.0, y=0.0, z=210.0)

    autonomy.step(current_tick=1)

    # When far away from home and courtyard dais, dais offset must be 0.0 (grounded at elev 20.0)
    assert abs(human_gm.pos.y - 20.0) < 0.01, (
        f"Deity walking far from home must be grounded at elevation 20.0, got {human_gm.pos.y}"
    )

    # Now move deity within 5m of home
    human_gm.pos = Vec3(x=human_gm.home_pos.x + 2.0, y=0.0, z=human_gm.home_pos.z)
    human_gm.target_pos = human_gm.home_pos.model_copy()

    autonomy.step(current_tick=2)

    # Within 8m of home, dais offset (+3.2) must be applied
    assert abs(human_gm.pos.y - (20.0 + 3.2)) < 0.01, (
        f"Deity on home dais must have dais offset 3.2 added (23.2), got {human_gm.pos.y}"
    )


def test_divine_autonomy_name_sync() -> None:
    mock_engine = MagicMock()
    mock_entity = MagicMock()
    mock_entity.bestowed_name = "Lady Sophia"
    entities: dict[DeitySlot, Any] = {"gm_human": mock_entity}
    mock_engine.divine_hierarchy = MagicMock()
    mock_engine.divine_hierarchy.entities = entities
    mock_engine.heightmap = MagicMock()
    mock_heightmap = mock_engine.heightmap
    mock_heightmap.get_elevation.return_value = 18.0

    autonomy = DivineAutonomyEngine(engine=mock_engine)
    assert autonomy.deities["gm_human"].name == "Human God-Mother"

    autonomy.step(current_tick=10)

    assert autonomy.deities["gm_human"].name == "Lady Sophia"
    records = autonomy.get_sync_records()
    human_rec = next(r for r in records if r.id == "gm_human")
    assert human_rec.name == "Lady Sophia"


def test_divine_autonomy_facing_yaw() -> None:
    autonomy = DivineAutonomyEngine(engine=None)
    deity = autonomy.deities["gm_elf"]
    deity.pos = Vec3(x=0.0, y=0.0, z=0.0)
    # Moving along -Z (straight forward in Godot): dx=0, dz=-10
    deity.target_pos = Vec3(x=0.0, y=0.0, z=-10.0)

    autonomy.step(current_tick=1)

    # In Godot, facing -Z has yaw 0.0: math.atan2(-dx, -dz) = atan2(0, 10) = 0.0
    assert abs(deity.yaw - 0.0) < 0.01, f"Expected yaw ~0.0 facing -Z, got {deity.yaw}"


def test_divine_autonomy_idle_startup_grounding() -> None:
    mock_engine = MagicMock()
    mock_heightmap = MagicMock()
    mock_heightmap.get_elevation.return_value = 25.0
    mock_engine.heightmap = mock_heightmap
    mock_engine.divine_hierarchy = MagicMock()
    mock_engine.divine_hierarchy.entities = {}

    autonomy = DivineAutonomyEngine(engine=mock_engine)
    # All deities on startup must have pos.y == 25.0 + dais_offset
    for slot, deity in autonomy.deities.items():
        expected_y = round(25.0 + deity.dais_offset, 2)
        assert abs(deity.pos.y - expected_y) < 0.01, (
            f"Deity {slot} on startup must be grounded at home dais {expected_y}, got {deity.pos.y}"
        )


def test_divine_autonomy_convene_council_grounding() -> None:
    mock_engine = MagicMock()
    mock_heightmap = MagicMock()
    # In Grand Palace Courtyard, ground elevation is 32.0m
    mock_heightmap.get_elevation.return_value = 32.0
    mock_engine.heightmap = mock_heightmap
    mock_engine.divine_hierarchy = MagicMock()
    mock_engine.divine_hierarchy.entities = {}

    autonomy = DivineAutonomyEngine(engine=mock_engine)
    autonomy.issue_god_order("CONVENE_COUNCIL")

    # Simulate steps until arrival at council spots
    for t in range(1, 1000):
        autonomy.step(current_tick=t)
        all_arrived = all(d.target_pos is None for d in autonomy.deities.values())
        if all_arrived:
            break

    # Check that all 5 God-Mothers arrived at elevation 32.0 (dais_offset 0.0)
    for slot in DEITY_COUNCIL_ORDER:
        gm = autonomy.deities[slot]
        assert gm.target_pos is None, f"{slot} should have arrived at council"
        assert abs(gm.pos.y - 32.0) < 0.05, (
            f"Council seat for {slot} must be at 32.0m without dais offset, got {gm.pos.y}"
        )
        # Check facing inward toward PALACE_COURTYARD_DAIS (0.0, 15.0)
        dx_in = PALACE_COURTYARD_DAIS.x - gm.pos.x
        dz_in = PALACE_COURTYARD_DAIS.z - gm.pos.z
        expected_yaw = round(math.atan2(-dx_in, -dz_in), 3)
        assert abs(gm.yaw - expected_yaw) < 0.05, (
            f"{slot} arrival yaw must face dais ({expected_yaw}), got {gm.yaw}"
        )

    # Check World Goddess faces +Z (toward council)
    wg = autonomy.deities["world_goddess"]
    expected_wg_yaw = round(math.atan2(0.0, -1.0), 3)
    assert abs(wg.yaw - expected_wg_yaw) < 0.05, (
        f"World Goddess must face +Z ({expected_wg_yaw}), got {wg.yaw}"
    )


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

    # 5 radial highway midpoints
    highways = {
        "Aurelia Highway": (177.68, 545.85),
        "Sylvanor Highway": (575.0, -1.0),
        "Drakonis Spire Highway": (177.68, -547.85),
        "Fenris Hold Highway": (-465.18, 336.98),
        "Malakor Highway": (-465.18, -338.98),
    }
    for name, (wx, wz) in highways.items():
        val = sample_mask(wx, wz)
        assert val >= 128, f"{name} midpoint ({wx}, {wz}) must have road weight >= 128, got {val}"
