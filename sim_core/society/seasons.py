"""
sim_core/society/seasons.py
Four-season scarcity cycle: 7 game days/season, 28 game days/year.
Controls hunger decay, infant exposure risk, wild food regeneration,
and season_progress shader uniforms for Sky3D v2.1.
Follows NEURAL_AND_LIFECYCLE_SPEC.md Section 5.4.
"""

from __future__ import annotations

from sim_core.config import DAYS_PER_SEASON, DAYS_PER_YEAR, SEASONS_PER_YEAR, TICKS_PER_GAME_DAY
from sim_core.schemas import Season

SEASONS_ORDER: list[Season] = ["SPRING", "SUMMER", "AUTUMN", "WINTER"]


class SeasonManager:
    """Computes calendar cycles, seasonal multipliers, and Sky3D shader parameters."""

    @staticmethod
    def get_season(day: int) -> Season:
        """Determines current season from 1-indexed simulation game day."""
        zero_day = max(0, day - 1)
        season_idx = (zero_day // DAYS_PER_SEASON) % SEASONS_PER_YEAR
        return SEASONS_ORDER[season_idx]

    @staticmethod
    def get_year(day: int) -> int:
        """Determines current 1-indexed calendar year."""
        zero_day = max(0, day - 1)
        return (zero_day // DAYS_PER_YEAR) + 1

    @staticmethod
    def get_season_progress(day: int, tick_in_day: int) -> float:
        """
        Calculates global season progress uniform in [0.0, 4.0) for Sky3D & shaders:
        0.0 = Start of Spring, 1.0 = Start of Summer, 2.0 = Start of Autumn, 3.0 = Start of Winter.
        """
        zero_day = max(0, day - 1)
        day_in_year = zero_day % DAYS_PER_YEAR
        frac_day = max(0.0, min(1.0, tick_in_day / float(TICKS_PER_GAME_DAY)))
        total_days_in_year = day_in_year + frac_day
        # Map 28 days to 4 seasons: each season is 7 days
        return (total_days_in_year / float(DAYS_PER_SEASON)) % 4.0

    @staticmethod
    def get_hunger_multiplier(
        season: Season,
        is_infant: bool = False,
        is_sheltered: bool = True,
        winter_resistance: float = 1.0,
    ) -> float:
        """
        Computes metabolic hunger decay rate:
        - Spring/Summer/Autumn: 1.0x
        - Winter: 1.6x base (2.2x for unsheltered infants), attenuated by winter_resistance.
        """
        if season != "WINTER":
            return 1.0

        res = max(0.5, winter_resistance)
        if is_infant and not is_sheltered:
            return 2.2 / res
        return 1.6 / res

    @staticmethod
    def get_wild_food_multiplier(season: Season) -> float:
        """
        Wild food regeneration multiplier:
        - Spring: 1.2x
        - Summer: 1.0x
        - Autumn: 1.3x (harvest surplus)
        - Winter: 0.4x (-60% scarcity)
        """
        if season == "SPRING":
            return 1.2
        if season == "SUMMER":
            return 1.0
        if season == "AUTUMN":
            return 1.3
        if season == "WINTER":
            return 0.4
        return 1.0
