"""
sim_core/world/regional_weather.py
Gradual Regional Weather System for Gaia 8km x 8km Concentric Open World.
Models drifting 2D weather cells (CLEAR, OVERCAST, RAIN, STORM, SNOW, ASH)
biased by biome topography (Demon caldera, Dragon peaks, Elf highlands, Human plains).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Literal

from sim_core.config import WORLD_MAX_X, WORLD_MAX_Z, WORLD_MIN_X, WORLD_MIN_Z
from sim_core.schemas import Season

WeatherType = Literal["CLEAR", "OVERCAST", "RAIN", "STORM", "SNOW", "ASH"]
ALL_WEATHER_TYPES: list[WeatherType] = ["CLEAR", "OVERCAST", "RAIN", "STORM", "SNOW", "ASH"]


@dataclass
class RegionalWeatherCell:
    cell_id: str
    weather_type: WeatherType
    center_x: float
    center_z: float
    radius: float
    velocity_x: float
    velocity_z: float
    intensity: float
    biome_bias: str


class RegionalWeatherEngine:
    """
    Simulates drifting 2D weather fronts and biome-biased microclimates across 8km x 8km map.
    Returns continuous blend weights and environmental parameters at arbitrary world coordinates.
    """

    def __init__(self, seed: int = 42) -> None:
        self.rng = random.Random(seed)
        self.cells: list[RegionalWeatherCell] = []
        self._init_default_cells()

    def _init_default_cells(self) -> None:
        """Initializes permanent biome anchor cells and drifting regional weather fronts."""
        self.cells = [
            # 1. Demon Caldera Permanent Volcanic Ash Plume (North-West)
            RegionalWeatherCell(
                cell_id="demon_caldera_ash",
                weather_type="ASH",
                center_x=-2400.0,
                center_z=-1650.0,
                radius=1900.0,
                velocity_x=0.08,
                velocity_z=0.04,
                intensity=0.95,
                biome_bias="DEMON_CALDERA",
            ),
            # 2. Dragon Obsidian Alpine Snow Cell (North-East)
            RegionalWeatherCell(
                cell_id="dragon_peaks_snow",
                weather_type="SNOW",
                center_x=2100.0,
                center_z=-2200.0,
                radius=1800.0,
                velocity_x=-0.05,
                velocity_z=0.06,
                intensity=0.90,
                biome_bias="DRAGON_PEAKS",
            ),
            # 3. Elf Sylvan Highlands Rain & Mist Front (East)
            RegionalWeatherCell(
                cell_id="elf_highlands_rain",
                weather_type="RAIN",
                center_x=2100.0,
                center_z=600.0,
                radius=1700.0,
                velocity_x=0.06,
                velocity_z=0.08,
                intensity=0.85,
                biome_bias="ELF_HIGHLANDS",
            ),
            # 4. Human Sunlit Plains Clear Cell (South-East)
            RegionalWeatherCell(
                cell_id="human_plains_clear",
                weather_type="CLEAR",
                center_x=1200.0,
                center_z=2000.0,
                radius=1900.0,
                velocity_x=-0.06,
                velocity_z=-0.04,
                intensity=0.90,
                biome_bias="HUMAN_PLAINS",
            ),
            # 5. Beasthuman Taiga Overcast Squall (South-West)
            RegionalWeatherCell(
                cell_id="beast_taiga_overcast",
                weather_type="OVERCAST",
                center_x=-2100.0,
                center_z=1800.0,
                radius=1800.0,
                velocity_x=0.07,
                velocity_z=-0.05,
                intensity=0.80,
                biome_bias="BEAST_TAIGA",
            ),
            # 6. Wandering Ocean Squall Front (Ring 2/3 Drift)
            RegionalWeatherCell(
                cell_id="drifting_ocean_storm",
                weather_type="STORM",
                center_x=2800.0,
                center_z=-2800.0,
                radius=1600.0,
                velocity_x=-0.12,
                velocity_z=0.10,
                intensity=0.75,
                biome_bias="OCEAN_DRIFT",
            ),
        ]

    def step(self, current_tick: int, season: Season = "SPRING") -> None:
        """
        Advances weather cell drift and updates seasonal intensity.
        Called once per simulation tick or civic interval.
        """
        for cell in self.cells:
            # Advance drift
            cell.center_x += cell.velocity_x
            cell.center_z += cell.velocity_z

            # Bounce / wrap within bounds
            if cell.center_x < WORLD_MIN_X - 500.0:
                cell.center_x = WORLD_MAX_X + 400.0
            elif cell.center_x > WORLD_MAX_X + 500.0:
                cell.center_x = WORLD_MIN_X - 400.0

            if cell.center_z < WORLD_MIN_Z - 500.0:
                cell.center_z = WORLD_MAX_Z + 400.0
            elif cell.center_z > WORLD_MAX_Z + 500.0:
                cell.center_z = WORLD_MIN_Z - 400.0

            # Subtle breathing cycle on radius and intensity
            breathe = math.sin((current_tick * 0.01) + (hash(cell.cell_id) % 100))
            cell.intensity = max(0.4, min(1.0, cell.intensity + breathe * 0.001))

            # Seasonal modulation
            if season == "WINTER":
                if cell.weather_type == "RAIN":
                    cell.weather_type = "SNOW"
                elif cell.weather_type == "OVERCAST" and cell.biome_bias == "BEAST_TAIGA":
                    cell.weather_type = "SNOW"
            elif season == "SUMMER":
                if cell.weather_type == "SNOW" and cell.biome_bias != "DRAGON_PEAKS":
                    cell.weather_type = "RAIN"

    def sample_weather_at(self, x: float, z: float) -> dict[str, Any]:
        """
        Samples composite weather at world coordinates (x, z).
        Returns normalized blend weights, primary weather condition, fog, and sky tint.
        """
        weights: dict[WeatherType, float] = {w: 0.0 for w in ALL_WEATHER_TYPES}
        # Baseline world ambient condition is CLEAR with moderate weight
        weights["CLEAR"] = 0.30

        total_wind_x = 0.0
        total_wind_z = 0.0

        for cell in self.cells:
            dist = math.sqrt((x - cell.center_x) ** 2 + (z - cell.center_z) ** 2)
            if dist < cell.radius:
                w = (1.0 - (dist / cell.radius)) * cell.intensity
                weights[cell.weather_type] += w
                total_wind_x += cell.velocity_x * w * 10.0
                total_wind_z += cell.velocity_z * w * 10.0

        total_weight = sum(weights.values())
        if total_weight <= 0.0:
            total_weight = 1.0

        norm_weights: dict[str, float] = {k: round(v / total_weight, 4) for k, v in weights.items()}

        # Select primary weather state
        primary = max(weights.keys(), key=lambda k: weights[k])

        # Environmental parameters
        wind_strength = math.sqrt(total_wind_x**2 + total_wind_z**2)

        # Fog density based on weather composition
        fog_density = (
            norm_weights["CLEAR"] * 0.0006
            + norm_weights["OVERCAST"] * 0.0028
            + norm_weights["RAIN"] * 0.0065
            + norm_weights["STORM"] * 0.0125
            + norm_weights["SNOW"] * 0.0085
            + norm_weights["ASH"] * 0.0160
        )

        # Sky color tint based on weather composition
        sky_r = (
            norm_weights["CLEAR"] * 1.00
            + norm_weights["OVERCAST"] * 0.72
            + norm_weights["RAIN"] * 0.55
            + norm_weights["STORM"] * 0.35
            + norm_weights["SNOW"] * 0.85
            + norm_weights["ASH"] * 0.48
        )
        sky_g = (
            norm_weights["CLEAR"] * 0.98
            + norm_weights["OVERCAST"] * 0.75
            + norm_weights["RAIN"] * 0.60
            + norm_weights["STORM"] * 0.38
            + norm_weights["SNOW"] * 0.88
            + norm_weights["ASH"] * 0.36
        )
        sky_b = (
            norm_weights["CLEAR"] * 0.92
            + norm_weights["OVERCAST"] * 0.82
            + norm_weights["RAIN"] * 0.68
            + norm_weights["STORM"] * 0.45
            + norm_weights["SNOW"] * 0.95
            + norm_weights["ASH"] * 0.32
        )

        return {
            "primary_weather": primary,
            "intensity": round(norm_weights[primary], 4),
            "blend_weights": norm_weights,
            "wind_vector": (round(total_wind_x, 3), round(total_wind_z, 3)),
            "wind_strength": round(wind_strength, 3),
            "fog_density": round(fog_density, 5),
            "sky_tint": (round(sky_r, 3), round(sky_g, 3), round(sky_b, 3)),
        }
