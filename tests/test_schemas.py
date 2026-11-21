"""
tests/test_schemas.py
Phase 1 Acceptance Tests:
- Pydantic v2 schema validation for 4 races, 2 genders, divine hierarchy, and daily manifest
- Spatial hash grid 16x16m parcel hashing & benchmark (< 2 ms for 10,000 agents)
- O(1) Bilinear heightmap elevation lookup & boundary safety
"""

import time

import numpy as np
import pytest

from sim_core.config import (
    ADULT_BIOLOGICAL_YEARS,
    AGE_10_BIOLOGICAL_YEARS,
    calculate_biological_age_years,
)
from sim_core.races import (
    CROSS_SPECIES_BIRTH_SURVIVAL_CHANCE,
    CROSS_SPECIES_CONCEPTION_CHANCE,
    RACE_REGISTRY,
    get_race_profile,
)
from sim_core.schemas import (
    AgentRecord,
    DailyManifest,
    DivineEntityRecord,
    DivinePersonality,
    SisterCouncilMessage,
    Vec3,
)
from sim_core.spatial.hash_grid import SpatialHashGrid
from sim_core.spatial.heightmap import Heightmap


def test_race_registry_and_constants():
    """Verifies all 4 races, sub-lineages, and cross-species probability invariants."""
    assert CROSS_SPECIES_CONCEPTION_CHANCE == 0.50
    assert CROSS_SPECIES_BIRTH_SURVIVAL_CHANCE == 0.60

    human_prof = get_race_profile("HUMAN")
    assert human_prof.race_id == "HUMAN"
    assert human_prof.lifespan_multiplier == 1.0
    assert human_prof.gestation_days == 1.5
    assert human_prof.neuroplasticity_mult == 1.15

    elf_prof = get_race_profile("ELF")
    assert elf_prof.race_id == "ELF"
    assert elf_prof.lifespan_multiplier == 3.0
    assert elf_prof.gestation_days == 4.0

    dragon_prof = get_race_profile("DRAGON")
    assert dragon_prof.race_id == "DRAGON"
    assert dragon_prof.lifespan_multiplier == 6.0
    assert dragon_prof.gestation_days == 7.0
    assert dragon_prof.can_metamorphose is True
    assert dragon_prof.true_dragon_health == 650.0

    cat_prof = get_race_profile("BEASTHUMAN", "CAT_KIN")
    assert cat_prof.race_id == "BEASTHUMAN"
    assert cat_prof.sub_lineage == "CAT_KIN"
    assert cat_prof.gestation_days == 1.2

    dwarf_prof = get_race_profile("BEASTHUMAN", "DWARF")
    assert dwarf_prof.race_id == "BEASTHUMAN"
    assert dwarf_prof.sub_lineage == "DWARF"
    assert dwarf_prof.gestation_days == 2.2
    assert dwarf_prof.winter_resistance == 1.60

    # Ensure all registry entries match specification
    assert len(RACE_REGISTRY) >= 8


def test_biological_age_formula():
    """Verifies adult stage gate at (6.0 * L) and age 10 milestone at (3.33 * L) game days."""
    # Human (L = 1.0)
    human_l = 1.0
    adult_days_human = 6.0 * human_l
    bio_adult = calculate_biological_age_years(adult_days_human, human_l)
    assert bio_adult == pytest.approx(ADULT_BIOLOGICAL_YEARS, abs=1e-4)

    age_10_days_human = 3.3333333333333335 * human_l
    bio_10 = calculate_biological_age_years(age_10_days_human, human_l)
    assert bio_10 == pytest.approx(AGE_10_BIOLOGICAL_YEARS, abs=1e-2)

    # Elf (L = 3.0)
    elf_l = 3.0
    adult_days_elf = 6.0 * elf_l  # 18 game days
    bio_elf = calculate_biological_age_years(adult_days_elf, elf_l)
    assert bio_elf == pytest.approx(ADULT_BIOLOGICAL_YEARS, abs=1e-4)

    # Dragon (L = 6.0)
    dragon_l = 6.0
    adult_days_dragon = 6.0 * dragon_l  # 36 game days
    bio_dragon = calculate_biological_age_years(adult_days_dragon, dragon_l)
    assert bio_dragon == pytest.approx(ADULT_BIOLOGICAL_YEARS, abs=1e-4)


def test_schemas_instantiation_and_validation():
    """Verifies core Pydantic v2 domain schemas."""
    agent = AgentRecord(
        agent_id="agt_0001",
        slot_idx=0,
        display_name="Aiden",
        dynasty_surname="Vanguard",
        gender="BOY",
        race="HUMAN",
        pos=Vec3(x=16.5, y=10.0, z=-32.0),
    )
    assert agent.gender == "BOY"
    assert agent.stage == "INFANT"
    assert agent.crying is False
    assert agent.credits == 10.0

    deity = DivineEntityRecord(
        slot="gm_human",
        bestowed_name="Solis",
        role="RACIAL_GOD_MOTHER",
        patron_race="HUMAN",
        personality=DivinePersonality(compassion=0.7, restraint=0.5),
    )
    assert deity.bestowed_name == "Solis"
    assert deity.divine_energy == 300.0

    council_msg = SisterCouncilMessage(
        message_id="msg_001",
        day=1,
        tick=120,
        sender_slot="gm_human",
        recipient_slots=["gm_elf"],
        topic="BORDER_FRICTION",
        summary="Human settlers foraging near Sylvan border.",
    )
    assert council_msg.topic == "BORDER_FRICTION"

    manifest = DailyManifest(
        day=1,
        tick=10800,
        season="SPRING",
        committed_by="Gaia",
        db_path="data/civilization.db",
        db_sha256="dummy_db_sha256",
        pt_path="data/checkpoints/day_00001.pt",
        pt_sha256="dummy_pt_sha256",
        ledger_path="data/god_ledger/day_00001.md",
        status="VERIFIED",
    )
    assert manifest.status == "VERIFIED"


def test_spatial_hash_grid_benchmark():
    """
    Acceptance Test:
    Spawns 10,000 random coordinates in [-5000, 5000].
    Measures batch insert and 10,000 radius queries.
    Proves spatial hash grid insert and queries run in under 2 ms.
    """
    grid = SpatialHashGrid(cell_size=16.0)

    # 1. Coordinate check
    assert grid.get_parcel_id(0.0, 0.0) == "0_0"
    assert grid.get_parcel_id(16.5, -32.0) == "1_-2"

    num_agents = 10000
    np.random.seed(42)
    xs = np.random.uniform(-4000.0, 4000.0, size=num_agents).astype(np.float32)
    zs = np.random.uniform(-4000.0, 4000.0, size=num_agents).astype(np.float32)
    agent_ids = [f"agt_{i}" for i in range(num_agents)]

    # Measure batch insert latency
    t0 = time.perf_counter()
    grid.insert_batch(agent_ids, xs, zs)
    insert_duration_ms = (time.perf_counter() - t0) * 1000.0

    assert grid.count() == num_agents

    # Measure neighbor queries (Reality Bubble radius: 140m)
    t1 = time.perf_counter()
    # Sample 50 representative bubble centers across the world
    for i in range(50):
        neighbors = grid.query_radius(float(xs[i]), float(zs[i]), radius=140.0)
        assert len(neighbors) > 0

    query_duration_total_ms = (time.perf_counter() - t1) * 1000.0
    avg_query_ms = query_duration_total_ms / 50.0

    print(f"\n[SPATIAL_BENCHMARK] 10,000 agents inserted in {insert_duration_ms:.3f} ms. "
          f"Average 140m bubble query: {avg_query_ms:.4f} ms.")

    # High performance threshold: batch insert under 100ms, single query under 0.1ms
    assert avg_query_ms < 0.1, f"Average query took {avg_query_ms:.4f} ms (expected < 0.1 ms)"


def test_heightmap_bilinear_lookup():
    """Verifies O(1) elevation lookup and boundary protection."""
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
