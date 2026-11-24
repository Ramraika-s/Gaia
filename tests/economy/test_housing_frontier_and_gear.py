# tests/economy/test_housing_frontier_and_gear.py
from __future__ import annotations

from pathlib import Path

from sim_core.bridge.mock_adapter import MockWorldAdapter
from sim_core.engine import SimulationEngine
from sim_core.schemas import AgentRecord, BuildingRecord, ParcelRecord, Vec3
from sim_core.society.gear_economy import GearEconomyEngine
from sim_core.society.property import PropertyManager


def test_housing_market_double_entry_credit_conservation(engine: SimulationEngine) -> None:
    """Verifies that home purchases conserve credits with exactly 0.000000 drift."""
    bank = engine.bank
    housing = engine.housing_market

    # Create a test buyer
    buyer = AgentRecord(
        agent_id="test_buyer_01",
        slot_idx=0,
        race="HUMAN",
        gender="GIRL",
        stage="ADULT",
        age_ticks=5000,
        display_name="Elena",
        dynasty_surname="Vanguard",
        pos=Vec3(x=355.0, y=10.0, z=1090.0),
        credits=500.0,
        alive=True,
    )
    engine.agents[buyer.agent_id] = buyer

    # Calculate initial total credits
    initial_total = bank.reserve_credits + sum(a.credits for a in engine.agents.values())

    # Ensure there is a for-sale house
    target_bld: BuildingRecord | None = None
    for b in engine.city_layout.buildings.values():
        if b.for_sale and b.building_type == "HOUSE_T1_COTTAGE":
            target_bld = b
            break
    assert target_bld is not None, "Expected seed for-sale cottage in city layout"

    # Step housing market
    events = housing.step_housing_market(engine.agents, bank, current_tick=10)
    assert len(events) >= 1
    assert any(e["type"] == "HOUSE_PURCHASED" for e in events)

    # Verify ownership updated
    assert buyer.home_building_id is not None
    bought_bld = engine.city_layout.buildings[buyer.home_building_id]
    assert bought_bld.owner_id == buyer.agent_id
    assert not bought_bld.for_sale
    assert bought_bld.racial_style == buyer.race

    # Verify credit conservation
    final_total = bank.reserve_credits + sum(a.credits for a in engine.agents.values())
    drift = final_total - initial_total
    assert abs(drift) < 1e-6, f"Credit drift detected: {drift}"


def test_in_place_housing_tier_upgrades(engine: SimulationEngine) -> None:
    """Verifies that homeowners can upgrade cottages in-place (T1 -> T2 -> T3)."""
    bank = engine.bank
    housing = engine.housing_market

    homeowner = AgentRecord(
        agent_id="test_homeowner_02",
        slot_idx=1,
        race="ELF",
        gender="BOY",
        stage="ADULT",
        age_ticks=6000,
        display_name="Faelar",
        dynasty_surname="Silverleaf",
        pos=Vec3(x=1150.0, y=10.0, z=0.0),
        credits=600.0,
        alive=True,
    )
    engine.agents[homeowner.agent_id] = homeowner

    # Find and assign a cottage
    cottage: BuildingRecord | None = None
    for b in engine.city_layout.buildings.values():
        if b.building_type == "HOUSE_T1_COTTAGE":
            cottage = b
            break
    assert cottage is not None

    cottage.owner_id = homeowner.agent_id
    cottage.owner_name = f"{homeowner.display_name} {homeowner.dynasty_surname}"
    cottage.for_sale = False
    homeowner.home_building_id = cottage.building_id

    initial_total = bank.reserve_credits + sum(a.credits for a in engine.agents.values())

    # Step market -> should trigger T1 -> T2 upgrade
    events = housing.step_housing_market(engine.agents, bank, current_tick=20)
    assert any(
        e["type"] == "HOUSE_UPGRADED" and e["new_tier"] == "HOUSE_T2_TOWNHOUSE" for e in events
    )
    assert cottage.building_type == "HOUSE_T2_TOWNHOUSE"
    assert cottage.footprint_radius == 11.0

    # Step market again -> homeowner still has credits >= 360, triggers T2 -> T3 upgrade
    events2 = housing.step_housing_market(engine.agents, bank, current_tick=21)
    assert any(e["type"] == "HOUSE_UPGRADED" and e["new_tier"] == "HOUSE_T3_MANOR" for e in events2)
    assert cottage.building_type == "HOUSE_T3_MANOR"
    assert cottage.footprint_radius == 14.0

    final_total = bank.reserve_credits + sum(a.credits for a in engine.agents.values())
    assert abs(final_total - initial_total) < 1e-6, "Credit drift detected in tier upgrades"


def test_ring_2_frontier_pioneers_and_village_clustering(engine: SimulationEngine) -> None:
    """Verifies that pioneers claim Ring 2 plots on dry land and cluster into villages."""
    bank = engine.bank
    housing = engine.housing_market

    # Create 3 adventurous homeless pioneers
    pioneers = []
    for i in range(3):
        p = AgentRecord(
            agent_id=f"pioneer_{i + 1}",
            slot_idx=10 + i,
            race="BEASTHUMAN",
            gender="BOY" if i % 2 == 0 else "GIRL",
            stage="ADULT",
            age_ticks=4000,
            display_name=f"Grim_{i + 1}",
            dynasty_surname="Wildstrider",
            pos=Vec3(x=1600.0, y=12.0, z=50.0),
            credits=250.0,
            alive=True,
        )
        engine.agents[p.agent_id] = p
        pioneers.append(p)

    initial_total = bank.reserve_credits + sum(a.credits for a in engine.agents.values())

    # Step pioneers
    blds1 = housing.step_frontier_pioneers(engine.agents, bank, current_tick=40)
    assert len(blds1) >= 1
    pioneer_bld = blds1[0]

    # Verify coordinates are in Ring 2 (1500m <= r <= 3300m)
    r = (pioneer_bld.x**2 + pioneer_bld.z**2) ** 0.5
    assert 1500.0 <= r <= 3300.0
    assert pioneer_bld.y >= 4.0, "Pioneer building must be on dry land (y >= 4.0m)"
    assert pioneer_bld.is_frontier is True

    # city_layout wilderness invariant must pass because is_frontier is True
    valid, msg = engine.city_layout.verify_ring_2_wilderness()
    assert valid, f"Ring 2 check failed: {msg}"

    # Verify credit conservation
    final_total = bank.reserve_credits + sum(a.credits for a in engine.agents.values())
    assert abs(final_total - initial_total) < 1e-6

    # Test emergent village clustering
    # Manually cluster 3 frontier buildings within 60m of each other
    bld_a = BuildingRecord(
        building_id="bld_frontier_c1",
        city_id="frontier",
        building_type="HOUSE_T1_COTTAGE",
        racial_style="BEASTHUMAN",
        x=2000.0,
        y=15.0,
        z=500.0,
        rotation_y=0.0,
        parcel_x=125,
        parcel_z=31,
        owner_id="pioneer_1",
        owner_name="Grim Wildstrider",
        is_frontier=True,
    )
    bld_b = BuildingRecord(
        building_id="bld_frontier_c2",
        city_id="frontier",
        building_type="HOUSE_T1_COTTAGE",
        racial_style="BEASTHUMAN",
        x=2020.0,
        y=15.0,
        z=510.0,
        rotation_y=0.0,
        parcel_x=126,
        parcel_z=31,
        owner_id="pioneer_2",
        owner_name="Kira Wildstrider",
        is_frontier=True,
    )
    bld_c = BuildingRecord(
        building_id="bld_frontier_c3",
        city_id="frontier",
        building_type="HOUSE_T1_COTTAGE",
        racial_style="BEASTHUMAN",
        x=2010.0,
        y=15.0,
        z=530.0,
        rotation_y=0.0,
        parcel_x=125,
        parcel_z=33,
        owner_id="pioneer_3",
        owner_name="Boran Wildstrider",
        is_frontier=True,
    )

    for b in (bld_a, bld_b, bld_c):
        engine.city_layout.buildings[b.building_id] = b
        housing.frontier_buildings[b.building_id] = b

    housing._check_frontier_village_clustering(current_tick=45)
    assert len(housing.frontier_villages) >= 1
    village = list(housing.frontier_villages.values())[0]
    assert village.tier == "VILLAGE"
    assert bld_a.settlement_id == village.settlement_id
    assert bld_b.settlement_id == village.settlement_id
    assert bld_c.settlement_id == village.settlement_id


def test_gear_economy_crafting_and_profession_equipping(engine: SimulationEngine) -> None:
    """Verifies gear crafting, autonomous purchase, and profession-matched equipping."""
    bank = engine.bank
    gear_econ = engine.gear_economy

    # Create Merchant/Smith, Knight, and Farmer
    smith = AgentRecord(
        agent_id="test_smith",
        slot_idx=20,
        race="HUMAN",
        gender="BOY",
        stage="ADULT",
        role="MERCHANT",
        display_name="Tobias",
        dynasty_surname="Blacksmith",
        credits=200.0,
        alive=True,
    )
    knight = AgentRecord(
        agent_id="test_knight",
        slot_idx=21,
        race="HUMAN",
        gender="GIRL",
        stage="ADULT",
        role="PALACE_KNIGHT",
        display_name="Valeria",
        dynasty_surname="Ironclad",
        credits=300.0,
        alive=True,
    )
    farmer = AgentRecord(
        agent_id="test_farmer",
        slot_idx=22,
        race="HUMAN",
        gender="BOY",
        stage="ADULT",
        role="FARMER",
        display_name="Garth",
        dynasty_surname="Plowman",
        credits=150.0,
        alive=True,
    )

    engine.agents[smith.agent_id] = smith
    engine.agents[knight.agent_id] = knight
    engine.agents[farmer.agent_id] = farmer

    initial_total = bank.reserve_credits + sum(a.credits for a in engine.agents.values())

    # Step gear economy
    events = gear_econ.step_gear_economy(engine.agents, bank, current_tick=50)
    assert len(events) >= 1

    # Verify knight equipped gear
    assert "SWORD" in knight.equipped_gear or "KNIGHT_PLATE" in knight.equipped_gear
    # Verify farmer equipped gear
    assert "HOE" in farmer.equipped_gear or "PEASANT_TUNIC" in farmer.equipped_gear

    # Verify Reality Bubble rig includes equipped_gear
    engine.god_avatar_pos = Vec3(x=0.0, y=0.0, z=0.0)
    knight.pos = Vec3(x=10.0, y=0.0, z=10.0)
    engine.step_tick()

    mock_adapter: MockWorldAdapter = engine.adapter  # type: ignore
    assert len(mock_adapter.bubble_agents) > 0
    rig = next(
        (r for r in mock_adapter.bubble_agents if r["agent_id"] == knight.agent_id),
        None,
    )
    assert rig is not None
    assert "equipped_gear" in rig
    assert isinstance(rig["equipped_gear"], list)

    # Verify credit conservation
    final_total = bank.reserve_credits + sum(a.credits for a in engine.agents.values())
    assert abs(final_total - initial_total) < 1e-6, "Credit drift in gear economy"


def test_strict_credit_conservation_across_all_economic_actions(tmp_path: Path) -> None:
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

    assert abs(get_system_total() - baseline_total) < 1e-6
    assert bank.reserve_credits == 1_000_000.0 - 4800.0

    # 2. Execute city_layout.buy_building() with bank
    buyer = engine.spawn_agent(race="HUMAN", gender="GIRL", stage="ADULT", initial_credits=500.0)
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

    # 4. Multi-parcel probate without credit duplication
    deceased = engine.spawn_agent(race="HUMAN", gender="BOY", stage="ADULT", initial_credits=250.0)
    deceased.alive = False

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
    assert engine.political_engine.polities["sylvanor"].treasury_credits == treasury_before + 250.0
    assert abs(get_system_total() - baseline_total) < 1e-6

    # 5. In-place housing tier upgrade
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
    ok = gear_econ.craft_item(blacksmith, "HOE", bank)
    assert ok is True
    assert abs(get_system_total() - baseline_total) < 1e-6
    gear_econ.step_gear_economy(engine.agents, bank, current_tick=10)
    assert abs(get_system_total() - baseline_total) < 1e-6

    # 7. Frontier village clustering with 0.0 initial unbacked treasury
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
