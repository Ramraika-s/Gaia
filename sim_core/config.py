"""
sim_core/config.py
Master configuration constants, pacing parameters, LOD tiers, and world boundaries
for the Gaia Persistent Unbounded Multi-Race AI Civilization Engine.
"""

from __future__ import annotations

import random
from typing import Final, Literal

# ==============================================================================
# 1. Pacing & Time Constants
# ==============================================================================

# Default: 1.5 real hours (5400s) = 1 game day. Tunable 3600-7200s.
REAL_SECONDS_PER_GAME_DAY: Final[int] = 5400

# Base cognitive tick rate is 2 Hz (2 ticks per real second at 1x speed)
COGNITIVE_TICK_RATE_HZ: Final[float] = 2.0
# 10,800 ticks per game day at default 5400s
TICKS_PER_GAME_DAY: Final[int] = int(REAL_SECONDS_PER_GAME_DAY * COGNITIVE_TICK_RATE_HZ)

# Civic, political, WTC, and health tick occurs every 60 sim ticks (~30 real seconds at 1x)
CIVIC_TICK_INTERVAL_TICKS: Final[int] = 60

# Calendar pacing
DAYS_PER_SEASON: Final[int] = 7
SEASONS_PER_YEAR: Final[int] = 4
DAYS_PER_YEAR: Final[int] = DAYS_PER_SEASON * SEASONS_PER_YEAR  # 28 Game Days
TICKS_PER_SEASON: Final[int] = DAYS_PER_SEASON * TICKS_PER_GAME_DAY  # 75,600 ticks
TICKS_PER_YEAR: Final[int] = DAYS_PER_YEAR * TICKS_PER_GAME_DAY  # 302,400 ticks

# Cognitive Multi-Tier LOD
LOD_TIER_0_HZ: Final[float] = 2.0    # In Reality Bubble (120-160m): 2 Hz
LOD_TIER_1_HZ: Final[float] = 1.0    # Distant awake agents: 1 Hz
LOD_TIER_2_HZ: Final[float] = 0.25   # Distant sleeping / sheltered idle: 0.25 Hz

# Reality Bubble parameters
REALITY_BUBBLE_RADIUS_METERS: Final[float] = 140.0
REALITY_BUBBLE_MAX_RIGS: Final[int] = 120
ORBITAL_MAP_ALTITUDE_METERS: Final[float] = 250.0

# ==============================================================================
# 2. Memory, Slabs & Hardware Discipline
# ==============================================================================

# Contiguous neural/spatial allocation slab size (Unbounded scaling)
SLAB_SIZE: Final[int] = 2048

# Host RAM watermark monitoring via psutil
SOFT_RAM_WATERMARK_PERCENT: Final[float] = 75.0

# ==============================================================================
# 3. Spatial World & Parcel Boundaries
# ==============================================================================

# 10,000m x 10,000m world centered around (0, 0)
WORLD_SIZE_X: Final[float] = 10000.0
WORLD_SIZE_Z: Final[float] = 10000.0
WORLD_MIN_X: Final[float] = -5000.0
WORLD_MAX_X: Final[float] = 5000.0
WORLD_MIN_Z: Final[float] = -5000.0
WORLD_MAX_Z: Final[float] = 5000.0

# Explicit 16x16m parcel chunk grid
PARCEL_SIZE: Final[float] = 16.0
PARCEL_COUNT_X: Final[int] = int(WORLD_SIZE_X / PARCEL_SIZE)  # 625 parcels
PARCEL_COUNT_Z: Final[int] = int(WORLD_SIZE_Z / PARCEL_SIZE)  # 625 parcels

# ==============================================================================
# 4. Biological Gates & Age Calibration
# ==============================================================================

# Age-10 Mixed-Race Patronage Milestone factor: 3.33 * Lifespan_Multiplier game days
AGE_10_BIOLOGICAL_YEARS: Final[float] = 10.0
ADULT_BIOLOGICAL_YEARS: Final[float] = 18.0
ELDER_BIOLOGICAL_YEARS: Final[float] = 60.0

# Cross-species reproduction probabilities
CROSS_SPECIES_CONCEPTION_CHANCE: Final[float] = 0.50
CROSS_SPECIES_BIRTH_SURVIVAL_CHANCE: Final[float] = 0.60
SAME_SPECIES_CONCEPTION_CHANCE: Final[float] = 1.00
SAME_SPECIES_BIRTH_SURVIVAL_CHANCE: Final[float] = 0.98

# Crying / Distress threshold
INFANT_CRYING_DISTRESS_THRESHOLD: Final[float] = 0.45

# Survival gate threshold in SharedSkillNet
SURVIVAL_GATE_HEALTH_HUNGER: Final[float] = 0.25


def calculate_biological_age_years(age_days: float, lifespan_multiplier: float) -> float:
    """
    Computes biological age in years for an agent given elapsed game days
    and race lifespan multiplier L.
    Adult threshold (18 bio years) occurs at exactly (6.0 * L) game days.
    Age 10 milestone occurs at exactly (3.33 * L) game days.
    """
    if lifespan_multiplier <= 0.0:
        lifespan_multiplier = 1.0
    return (age_days / (6.0 * lifespan_multiplier)) * ADULT_BIOLOGICAL_YEARS


def calculate_age_days(ticks: int) -> float:
    """Converts sim ticks to game days."""
    return ticks / TICKS_PER_GAME_DAY


# ==============================================================================
# 5. Settlement & Institution Thresholds
# ==============================================================================

SettlementTier = Literal["VILLAGE", "TOWN", "CITY", "STATE", "NATION"]

SETTLEMENT_TIER_REQUIREMENTS: Final[dict[SettlementTier, dict[str, float]]] = {
    "VILLAGE": {"min_population": 5, "min_parcels": 4, "min_treasury": 50.0},
    "TOWN": {"min_population": 25, "min_parcels": 16, "min_treasury": 250.0},
    "CITY": {"min_population": 100, "min_parcels": 48, "min_treasury": 1000.0},
    "STATE": {"min_population": 300, "min_parcels": 120, "min_treasury": 3500.0},
    "NATION": {"min_population": 800, "min_parcels": 250, "min_treasury": 10000.0},
}

# Free City multi-racial threshold
FREE_CITY_MIN_RACES: Final[int] = 2
FREE_CITY_MIN_RACE_SHARE: Final[float] = 0.15

# World Library Governance
MAX_ELDERS_PER_NATION: Final[int] = 2

# Default Bestowed Deity Names
DEFAULT_DEITY_NAMES: Final[dict[str, str]] = {
    "world_goddess": "Gaia",
    "gm_human": "Solis",
    "gm_elf": "Sylphira",
    "gm_dragon": "Ignis",
    "gm_beasthuman": "Fauna",
    "gm_demon": "Morvath",
}

# ==============================================================================
# 6. Seedable Deterministic RNG
# ==============================================================================

DEFAULT_SEED: Final[int] = 42


def set_global_seed(seed: int = DEFAULT_SEED) -> None:
    """Sets deterministic seed for Python random and NumPy."""
    import numpy as np
    import torch

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
