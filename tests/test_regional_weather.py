"""
tests/test_regional_weather.py
Verifies gradual regional weather cell simulation, drifting kinematics,
biome-biased weather sampling across 8km x 8km world, and seasonal modulation.
"""

from sim_core.world.regional_weather import RegionalWeatherEngine


def test_weather_engine_initialization_and_sampling():
    engine = RegionalWeatherEngine(seed=123)
    assert len(engine.cells) >= 6

    # 1. Demon Caldera Biome Bias: (-2400, -1650) should sample predominantly ASH
    sample_demon = engine.sample_weather_at(-2400.0, -1650.0)
    assert sample_demon["primary_weather"] == "ASH"
    assert sample_demon["blend_weights"]["ASH"] >= 0.40
    assert sample_demon["fog_density"] > 0.005
    assert sample_demon["sky_tint"][0] < 0.8  # Darker ash sky

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


def test_weather_cell_drift_and_bounds_safety():
    engine = RegionalWeatherEngine(seed=999)
    initial_x = engine.cells[0].center_x
    initial_z = engine.cells[0].center_z

    # Step simulation 120 ticks
    for tick in range(1, 121):
        engine.step(current_tick=tick, season="SPRING")

    # Verify positions drifted smoothly
    assert engine.cells[0].center_x != initial_x
    assert engine.cells[0].center_z != initial_z

    # Verify all cells stay within world bounds
    for cell in engine.cells:
        assert -4500.0 <= cell.center_x <= 4500.0
        assert -4500.0 <= cell.center_z <= 4500.0


def test_weather_seasonal_transition():
    engine = RegionalWeatherEngine(seed=42)

    # In Winter, rain cells turn to snow
    engine.step(current_tick=500, season="WINTER")
    rain_cells = [c for c in engine.cells if c.weather_type == "RAIN"]
    assert len(rain_cells) == 0, "No rain cells should persist in harsh winter"

    snow_cells = [c for c in engine.cells if c.weather_type == "SNOW"]
    assert len(snow_cells) >= 2


def test_weather_sampling_at_all_5_cities():
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
        assert sample["primary_weather"] in ["CLEAR", "OVERCAST", "RAIN", "STORM", "SNOW", "ASH"], (
            f"City {name} returned invalid primary weather"
        )
        w_sum = sum(sample["blend_weights"].values())
        assert abs(w_sum - 1.0) < 0.02, f"City {name} blend weights do not sum to 1.0"
        assert sample["wind_strength"] >= 0.0
        assert sample["fog_density"] > 0.0
