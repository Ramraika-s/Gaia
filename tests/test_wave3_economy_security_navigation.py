"""
tests/test_wave3_economy_security_navigation.py
Comprehensive regression suite for Gaia v4.0 Remediation Wave 3:
1. Strict Double-Entry Credit Conservation across all economic actions (0.000000 drift).
2. WTC Macro Baseline Calibration & Console Market Freeze parity.
3. Palace Security State Machine & Spatial Navigation Reconciliation.
4. Polities & 16x16m Border Registration for Ring 1 Cities & Frontier Villages.
5. Biome-Anchored Microclimate Weather Drift & Reversible Seasonal Weather.
"""

from __future__ import annotations

import math
from pathlib import Path

from scripts.launch_gaia import spawn_initial_population
from sim_core.bridge.mock_adapter import MockWorldAdapter
from sim_core.engine import SimulationEngine
from sim_core.god_console.cli import RichGodConsole
from sim_core.schemas import (
    BuildingRecord,
    PalacePass,
    ParcelRecord,
    SettlementRecord,
    Vec3,
)
from sim_core.society.gear_economy import GearEconomyEngine
from sim_core.society.property import PropertyManager
from sim_core.world.city_layout import CityLayoutEngine
from sim_core.world.palace_security import OUTER_BOUNDARY_RADIUS
from sim_core.world.regional_weather import RegionalWeatherEngine


def test_wave3_strict_credit_conservation_across_all_economic_actions(tmp_path: Path):
    """
    Verifies that credit creation, transactions, probate, gear, housing,
    and emergent frontier settlements maintain strictly 0.000000 credit drift.
    """
    engine = SimulationEngine(
        db_path=tmp_path / "civ_wave3.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        adapter=MockWorldAdapter(),
        headless=True,
    )

    bank = engine.bank
    assert bank.reserve_credits == 1_000_000.0

    def get_system_total() -> float:
        agent_credits = sum(a.credits for a in engine.agents.values())
        polity_credits = sum(p.treasury_credits for p in engine.political_engine.polities.values())
        return bank.reserve_credits + agent_credits + polity_credits

    baseline_total = get_system_total()

    # 1. Spawn 24 Palace Knights via spawn_knight_battalion
    knights = engine.palace_security.spawn_knight_battalion(engine.agents, count=24)
    assert len(knights) == 24
    for k in knights:
        assert k.credits == 200.0
        assert k.profession == "KNIGHT"
        assert k.role == "PALACE_KNIGHT"

    # Total must be conserved (24 * 200 = 4800 debited from bank.reserve_credits)
    assert abs(get_system_total() - baseline_total) < 1e-6
    assert bank.reserve_credits == 1_000_000.0 - 4800.0

    # 2. Execute city_layout.buy_building() with bank
    buyer = engine.spawn_agent(race="HUMAN", gender="GIRL", stage="ADULT", initial_credits=500.0)
    # Target an unowned for-sale seed cottage
    seed_bld: BuildingRecord | None = None
    for b in engine.city_layout.buildings.values():
        if b.for_sale and b.building_type == "HOUSE_T1_COTTAGE":
            seed_bld = b
            break
    assert seed_bld is not None

    ok, msg = engine.city_layout.buy_building(seed_bld.building_id, buyer, bank=bank)
    assert ok, f"buy_building failed: {msg}"
    assert buyer.home_building_id == seed_bld.building_id
    assert seed_bld.owner_id == buyer.agent_id
    assert not seed_bld.for_sale
    assert abs(get_system_total() - baseline_total) < 1e-6

    # 3. Execute property_mgr.buy_parcel() with bank
    prop_mgr: PropertyManager = engine.property_mgr
    test_parcel = ParcelRecord(
        parcel_id="99_99",
        cx=99,
        cz=99,
        settlement_id="sylvanor",
        owner_id=None,
        owner_type="UNCLAIMED",
        assessed_value=120.0,
        for_sale_price=150.0,
    )
    prop_mgr.register_parcel(test_parcel)

    ok, msg = prop_mgr.buy_parcel(
        buyer=buyer,
        parcel_id="99_99",
        price=150.0,
        bank=bank,
    )
    assert ok, f"buy_parcel failed: {msg}"
    assert test_parcel.owner_id == buyer.agent_id
    assert abs(get_system_total() - baseline_total) < 1e-6

    # 4. Multi-parcel execute_probate_and_escheatment() without credit duplication
    deceased = engine.spawn_agent(race="HUMAN", gender="BOY", stage="ADULT", initial_credits=250.0)
    deceased.alive = False

    # Deceased owns 3 parcels: 2 in sylvanor, 1 in wilderness
    p1 = ParcelRecord(
        parcel_id="101_101",
        cx=101,
        cz=101,
        settlement_id="sylvanor",
        owner_id=deceased.agent_id,
        owner_type="INDIVIDUAL",
        assessed_value=100.0,
    )
    p2 = ParcelRecord(
        parcel_id="102_102",
        cx=102,
        cz=102,
        settlement_id="sylvanor",
        owner_id=deceased.agent_id,
        owner_type="INDIVIDUAL",
        assessed_value=120.0,
    )
    p3 = ParcelRecord(
        parcel_id="103_103",
        cx=103,
        cz=103,
        settlement_id=None,
        owner_id=deceased.agent_id,
        owner_type="INDIVIDUAL",
        assessed_value=80.0,
    )
    prop_mgr.register_parcel(p1)
    prop_mgr.register_parcel(p2)
    prop_mgr.register_parcel(p3)

    treasury_before = engine.political_engine.polities["sylvanor"].treasury_credits

    def credit_treasury(sid: str, amt: float) -> None:
        if sid in engine.political_engine.polities:
            engine.political_engine.polities[sid].treasury_credits += amt

    results = prop_mgr.execute_probate_and_escheatment(
        deceased=deceased,
        all_agents=engine.agents,
        settlement_treasury_credit_fn=credit_treasury,
        bank=bank,
    )
    assert len(results) == 3
    assert deceased.credits == 0.0
    # Exactly 250.0 credited once to sylvanor treasury, not duplicated across both sylvanor parcels!
    assert engine.political_engine.polities["sylvanor"].treasury_credits == treasury_before + 250.0
    assert abs(get_system_total() - baseline_total) < 1e-6

    # DEF-04: Wilderness escheatment fallback transfers remaining credits to bank reserve
    hermit = engine.spawn_agent(race="HUMAN", gender="BOY", stage="ADULT", initial_credits=180.0)
    hermit.alive = False
    p_wild = ParcelRecord(
        parcel_id="999_999", cx=999, cz=999, settlement_id=None,
        owner_id=hermit.agent_id, owner_type="INDIVIDUAL", assessed_value=50.0
    )
    prop_mgr.register_parcel(p_wild)
    bank_res_before = bank.reserve_credits
    prop_mgr.execute_probate_and_escheatment(
        deceased=hermit, all_agents=engine.agents, settlement_treasury_credit_fn=None, bank=bank
    )
    assert hermit.credits == 0.0
    assert bank.reserve_credits == bank_res_before + 180.0
    assert abs(get_system_total() - baseline_total) < 1e-6

    # DEF-05 & DEF-08: Rejection of bankless/sellerless purchases
    ok_p, err_p = prop_mgr.buy_parcel(buyer=buyer, parcel_id="999_999", bank=None, seller=None)
    assert not ok_p
    assert err_p == "BANK_OR_SELLER_REQUIRED"

    ok_b, err_b = engine.city_layout.buy_building(seed_bld.building_id, buyer, bank=None)
    # Note: when engine is attached, buy_building resolves engine.bank;
    # if bank is None and engine has no bank:
    dummy_layout = CityLayoutEngine(engine=None)
    dummy_bld = BuildingRecord(
        building_id="bld_dummy", city_id="aurelia", building_type="HOUSE_T1_COTTAGE",
        racial_style="HUMAN", x=0.0, y=0.0, z=0.0, rotation_y=0.0, parcel_x=0, parcel_z=0,
        footprint_radius=8.0, owner_id=None, owner_name=None, for_sale=True, sale_price=50.0
    )
    dummy_layout.buildings[dummy_bld.building_id] = dummy_bld
    dummy_buyer = engine.spawn_agent(
        race="HUMAN", gender="BOY", stage="ADULT", initial_credits=100.0
    )
    ok_b2, err_b2 = dummy_layout.buy_building("bld_dummy", dummy_buyer, bank=None)
    assert not ok_b2
    assert err_b2 == "BANK_OR_SELLER_REQUIRED"

    # DEF-09: Placeholder citizen_* buildings converted to for_sale=True in housing market
    placeholder_bld = BuildingRecord(
        building_id="bld_placeholder_seed", city_id="sylvanor", building_type="HOUSE_T1_COTTAGE",
        racial_style="ELF", x=1200.0, y=10.0, z=0.0, rotation_y=0.0, parcel_x=75, parcel_z=0,
        footprint_radius=8.0, owner_id="citizen_sylvanor_99", owner_name="Citizen Placeholder",
        for_sale=False, sale_price=100.0
    )
    engine.city_layout.buildings[placeholder_bld.building_id] = placeholder_bld
    engine.housing_market.step_housing_market(engine.agents, bank, current_tick=120)
    assert placeholder_bld.for_sale is True
    assert placeholder_bld.owner_id is None

    # 5. In-place housing tier upgrade (Cottage -> Townhouse)
    buyer.credits += 200.0
    bank.reserve_credits -= 200.0
    upgrades = engine.housing_market.step_housing_market(engine.agents, bank, current_tick=100)
    assert any(u["type"] == "HOUSE_UPGRADED" for u in upgrades)
    assert seed_bld.building_type == "HOUSE_T2_TOWNHOUSE"
    assert abs(get_system_total() - baseline_total) < 1e-6

    # 6. Gear economy crafting and purchase
    gear_econ: GearEconomyEngine = engine.gear_economy
    blacksmith = engine.spawn_agent(
        race="HUMAN", gender="BOY", stage="ADULT", role="BLACKSMITH", initial_credits=100.0
    )
    engine.spawn_agent(
        race="ELF", gender="GIRL", stage="ADULT", role="MERCHANT", initial_credits=100.0
    )
    # Craft hoe
    ok = gear_econ.craft_item(blacksmith, "HOE", bank)
    assert ok is True
    assert abs(get_system_total() - baseline_total) < 1e-6
    # Retail purchase
    gear_econ.step_gear_economy(engine.agents, bank, current_tick=10)
    assert abs(get_system_total() - baseline_total) < 1e-6

    # 7. Emergent Ring 2 frontier village creation
    pioneer = engine.spawn_agent(
        race="BEASTHUMAN", gender="BOY", stage="ADULT", initial_credits=300.0
    )
    pioneer.home_building_id = None
    spawned = engine.housing_market.step_frontier_pioneers(engine.agents, bank, current_tick=120)
    if spawned:
        assert abs(get_system_total() - baseline_total) < 1e-6

    # Emergent village clustering with 0.0 initial unbacked treasury
    cluster = [
        BuildingRecord(
            building_id=f"bld_test_cluster_{k}",
            city_id="frontier",
            building_type="HOUSE_T1_COTTAGE",
            racial_style="HUMAN",
            x=2000.0 + k * 10.0,
            y=12.0,
            z=2000.0 + k * 10.0,
            rotation_y=0.0,
            parcel_x=125,
            parcel_z=125,
            footprint_radius=8.0,
            owner_id="pioneer_1",
            owner_name="Pioneer Alpha",
            for_sale=False,
            sale_price=180.0,
            is_frontier=True,
        )
        for k in range(3)
    ]
    for b in cluster:
        engine.housing_market.frontier_buildings[b.building_id] = b
    engine.housing_market._check_frontier_village_clustering(current_tick=200)

    v_ids = list(engine.housing_market.frontier_villages.keys())
    assert len(v_ids) >= 1
    new_v = engine.housing_market.frontier_villages[v_ids[0]]
    assert new_v.treasury_credits == 0.0
    assert abs(get_system_total() - baseline_total) < 1e-6


def test_wave3_wtc_calibration_and_freeze(tmp_path: Path):
    """Verifies baseline CPI calibration at 1,500 agents and God Console market freeze."""
    engine = SimulationEngine(
        db_path=tmp_path / "civ_wtc.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        adapter=MockWorldAdapter(),
        headless=True,
    )

    spawn_initial_population(engine, num_agents=1500)
    assert len(engine.agents) >= 1500

    # CPI must start at exactly 1.000 after calibrate_baseline()
    assert abs(engine.wtc.cpi - 1.0) < 1e-4

    # DEF-03: Single-source-of-truth Q calculation preserves CPI=1.000 during civic loop step
    engine._step_civic_loop()
    assert abs(engine.wtc.cpi - 1.0) < 0.05

    cli = RichGodConsole(engine)
    assert engine.wtc.frozen is False

    # Freeze market via console
    out1 = cli._cmd_wtc_action(["freeze"])
    assert "frozen" in out1.lower()
    assert engine.wtc.frozen is True

    # Attempt order while frozen
    ok, reason = engine.wtc.place_order("agent_1", "BUY", "food", 10.0, 5.0)
    assert not ok
    assert reason == "MARKET_FROZEN"

    # Unfreeze market via console
    out2 = cli._cmd_wtc_action(["freeze"])
    assert "unfrozen" in out2.lower()
    assert engine.wtc.frozen is False


def test_wave3_palace_security_and_navigation_harmony(tmp_path: Path):
    """
    Verifies:
    1. Palace Knights run the KNIGHT profession network.
    2. Palace Knights & approved PalacePass holders enter/patrol palace interior (r < 90m)
       without being pushed out by NavigationEngine.
    3. Trespassers are pushed out and intercepted by at most 1 knight.
    4. Target knight assignment is released once target is escorted past OUTER_BOUNDARY_RADIUS.
    """
    engine = SimulationEngine(
        db_path=tmp_path / "civ_sec.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        adapter=MockWorldAdapter(),
        headless=True,
    )

    knights = engine.palace_security.spawn_knight_battalion(engine.agents, count=24)
    for k in knights:
        assert k.role == "PALACE_KNIGHT"
        assert k.profession == "KNIGHT"

    # Navigation harmony: allow_palace_interior allows walking within r < 90m
    next_x, next_z, _ = engine.navigation.resolve_world_movement(
        current_x=20.0,
        current_z=20.0,
        target_x=25.0,
        target_z=25.0,
        allow_palace_interior=True,
    )
    assert math.hypot(next_x, next_z) < 90.0

    # DEF-11: allow_palace_interior permits entry into God-Mother palaces (e.g. sylvanor_palace)
    syl_x, syl_z, _ = engine.navigation.resolve_world_movement(
        current_x=1150.0,
        current_z=5.0,
        target_x=1150.0,
        target_z=10.0,
        allow_palace_interior=True,
    )
    assert abs(syl_x - 1150.0) < 2.0

    # DEF-02: get_building_door_pos returns entrance outside collision radius
    bld_test = engine.city_layout.buildings["bld_sylvanor_seed_01"]
    door_vec = engine.navigation.get_building_door_pos("bld_sylvanor_seed_01", bld_test)
    assert door_vec is not None
    dist_door_to_center = math.hypot(door_vec.x - bld_test.x, door_vec.z - bld_test.z)
    assert dist_door_to_center >= bld_test.footprint_radius + 1.0

    # DEF-06: despawn_agent clears navigation path cache
    p_agent = engine.spawn_agent(
        race="HUMAN", gender="BOY", stage="ADULT", pos=Vec3(x=500.0, y=0.0, z=500.0)
    )
    engine.navigation.get_next_waypoint(
        p_agent.agent_id, p_agent.pos, Vec3(x=1000.0, y=0.0, z=1000.0)
    )
    assert p_agent.agent_id in engine.navigation._agent_path_cache
    engine.despawn_agent(p_agent.agent_id)
    assert p_agent.agent_id not in engine.navigation._agent_path_cache

    # DEF-07: Sub-45m straight path crossing curtain wall routes via gate
    p_out = Vec3(x=1395.0, y=0.0, z=30.0)
    p_in = Vec3(x=1370.0, y=0.0, z=0.0)
    wp = engine.navigation.get_next_waypoint("test_cross_wall", p_out, p_in)
    assert wp != p_in

    # Unapproved mortal without allow_palace_interior is pushed outside 90m
    out_x, out_z, _ = engine.navigation.resolve_world_movement(
        current_x=0.0,
        current_z=60.0,
        target_x=0.0,
        target_z=0.0,
        allow_palace_interior=False,
    )
    assert math.hypot(out_x, out_z) >= 90.0

    # Test PalacePass holder approval
    visitor = engine.spawn_agent(
        race="HUMAN", gender="BOY", stage="ADULT", pos=Vec3(x=0.0, y=32.0, z=36.0)
    )
    engine.palace_security.active_passes[visitor.agent_id] = PalacePass(
        pass_id="pass_vis_01",
        agent_id=visitor.agent_id,
        granted_by="WORLD_GODDESS",
        granted_tick=1,
        expires_tick=1000,
    )
    allow = engine.palace_security.is_whitelisted(
        visitor
    ) or engine.palace_security.has_active_pass(visitor.agent_id, 10)
    assert allow is True

    # Intruder interception: only 1 knight dispatched per intruder
    intruder = engine.spawn_agent(
        race="HUMAN", gender="BOY", stage="ADULT", pos=Vec3(x=0.0, y=32.0, z=50.0)
    )
    engine.palace_security._dispatch_intercept(intruder.agent_id)
    assigned_count = sum(
        1 for tid, _ in engine.palace_security.knight_targets.values() if tid == intruder.agent_id
    )
    assert assigned_count == 1

    # Second dispatch call does not create duplicate pile-on
    engine.palace_security._dispatch_intercept(intruder.agent_id)
    assigned_count_2 = sum(
        1 for tid, _ in engine.palace_security.knight_targets.values() if tid == intruder.agent_id
    )
    assert assigned_count_2 == 1

    # Target release past OUTER_BOUNDARY_RADIUS (130m)
    intruder.pos.x = 0.0
    intruder.pos.z = OUTER_BOUNDARY_RADIUS + 10.0
    engine.palace_security.reported_trespassers.add(intruder.agent_id)
    engine.palace_security._step_knights(engine.agents)

    active_targets = [tid for tid, _ in engine.palace_security.knight_targets.values()]
    assert intruder.agent_id not in active_targets
    assert intruder.agent_id not in engine.palace_security.reported_trespassers

    # DEF-01: Intercept subdues intruder, transitions to ESCORT, and shepherds past 130m
    intruder2 = engine.spawn_agent(
        race="HUMAN", gender="BOY", stage="ADULT", pos=Vec3(x=0.0, y=32.0, z=91.5)
    )
    engine.palace_security._dispatch_intercept(intruder2.agent_id)
    kid = [
        k for k, (t, m) in engine.palace_security.knight_targets.items() if t == intruder2.agent_id
    ][0]
    k_agent = engine.agents[kid]
    k_agent.pos.x = 0.0
    k_agent.pos.z = 92.5
    engine.palace_security._step_knights(engine.agents)
    assert engine.palace_security.knight_targets[kid][1] == "ESCORT"
    assert intruder2.stamina == 0.0
    for _ in range(45):
        engine.palace_security._step_knights(engine.agents)
    assert kid not in engine.palace_security.knight_targets
    assert intruder2.pos.z >= 130.0

    # DEF-10: City guard patrol step updates yaw and spatial_grid
    guards_syl = engine.city_layout.spawn_city_guard_garrison(engine.agents, "sylvanor", count=10)
    g1 = guards_syl[0]
    engine.city_layout.step_patrols(tick=20, agents_dict=engine.agents)
    assert g1.yaw != 0.0 or g1.pos.x != 0.0


def test_wave3_polities_and_borders(tmp_path: Path):
    """Verifies that all 5 Ring 1 cities and emergent villages are registered
    in political engine and border manager."""
    engine = SimulationEngine(
        db_path=tmp_path / "civ_borders.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        adapter=MockWorldAdapter(),
        headless=True,
    )

    expected_cities = {"sylvanor", "aurelia", "fenris_hold", "malakor", "drakonis_spire"}
    assert set(engine.political_engine.polities.keys()) == expected_cities

    # DEF-12: Each Ring 1 city holds >= 48 non-overlapping border parcels (49 parcels)
    all_city_parcels: set[str] = set()
    for cid in expected_cities:
        p = engine.political_engine.polities[cid]
        assert p.tier == "CITY"
        assert cid in engine.border_mgr.settlement_borders
        city_border = engine.border_mgr.settlement_borders[cid]
        assert len(city_border) >= 48
        assert all_city_parcels.isdisjoint(city_border)
        all_city_parcels.update(city_border)

    # Register emergent frontier village
    new_village = SettlementRecord(
        settlement_id="village_frontier_99",
        name="Frontier Hold",
        tier="VILLAGE",
        founder_id="founder_1",
        center_pos=Vec3(x=1800.0, y=14.0, z=1800.0),
        treasury_credits=0.0,
        founded_tick=50,
    )
    ok = engine.border_mgr.register_settlement(new_village)
    assert ok is True
    assert "village_frontier_99" in engine.border_mgr.settlement_borders


def test_wave3_weather_anchoring_and_reversibility():
    """
    Verifies that:
    1. demon_caldera_ash stays anchored within 350m of (-2400, -1650) across 5,000 ticks.
    2. Seasonal weather transitions revert cleanly without permanent mutation.
    """
    weather = RegionalWeatherEngine(seed=42)
    ash_cell = next(c for c in weather.cells if c.cell_id == "demon_caldera_ash")
    taiga_cell = next(c for c in weather.cells if c.cell_id == "beast_taiga_overcast")

    # Step through 5,000 ticks across seasons
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

    # Biome cell anchoring verification
    dist_anchor = math.hypot(ash_cell.center_x - (-2400.0), ash_cell.center_z - (-1650.0))
    assert dist_anchor <= 350.0 + 1e-3, f"Ash cell drifted {dist_anchor:.2f}m (> 350m)"
    assert ash_cell.weather_type == "ASH"

    # Reversible seasonal modulation verification
    weather.step(current_tick=5001, season="WINTER")
    assert taiga_cell.weather_type == "SNOW"

    weather.step(current_tick=5002, season="SPRING")
    assert taiga_cell.weather_type == "OVERCAST"

    weather.step(current_tick=5003, season="SUMMER")
    assert taiga_cell.weather_type == "OVERCAST"
