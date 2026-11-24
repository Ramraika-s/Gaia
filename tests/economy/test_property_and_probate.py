# tests/economy/test_property_and_probate.py
from __future__ import annotations

from sim_core.engine import SimulationEngine
from sim_core.schemas import AgentRecord, BuildingRecord, ParcelRecord
from sim_core.society.property import PropertyManager
from sim_core.world.city_layout import CityLayoutEngine


def test_property_probate_cascade_and_escheatment() -> None:
    """
    Verifies 16x16m property probate cascade:
    - Heir inheritance (spouse / children).
    - Heirless death inside settlement escheats to settlement treasury.
    - Heirless death in wilderness reverts to UNCLAIMED (None).
    """
    prop_mgr = PropertyManager()

    # 1. Register parcel in settlement "town_solis"
    p1 = ParcelRecord(
        parcel_id="10_10",
        cx=10,
        cz=10,
        owner_id="agent_alice",
        settlement_id="town_solis",
        assessed_value=200.0,
    )
    prop_mgr.register_parcel(p1)
    assert p1.owner_id == "agent_alice"
    assert p1.settlement_id == "town_solis"

    # Alice has a spouse Bob
    alice = AgentRecord(
        agent_id="agent_alice",
        slot_idx=1,
        display_name="Alice",
        dynasty_surname="Vanguard",
        gender="GIRL",
        spouse_id="agent_bob",
        stage="ADULT",
        credits=50.0,
    )
    bob = AgentRecord(
        agent_id="agent_bob",
        slot_idx=2,
        display_name="Bob",
        dynasty_surname="Vanguard",
        gender="BOY",
        stage="ADULT",
        credits=50.0,
    )
    all_agents = {"agent_alice": alice, "agent_bob": bob}

    # Alice dies -> Bob inherits via probate cascade
    results1 = prop_mgr.execute_probate_and_escheatment(deceased=alice, all_agents=all_agents)
    assert len(results1) == 1
    assert results1[0] == ("10_10", "PROBATE_HEIR", "agent_bob")
    assert prop_mgr.parcels["10_10"].owner_id == "agent_bob"

    # 2. Bob dies with NO heirs inside settlement "town_solis" -> escheats to settlement treasury
    bob.spouse_id = None
    bob.parent_ids = []
    results2 = prop_mgr.execute_probate_and_escheatment(deceased=bob, all_agents=all_agents)
    assert len(results2) == 1
    assert results2[0] == ("10_10", "ESCHEATMENT_SETTLEMENT", "town_solis")
    assert prop_mgr.parcels["10_10"].owner_id == "town_solis"

    # 3. Wilderness parcel (outside all settlements) owned by heirless hermit Charlie
    charlie = AgentRecord(
        agent_id="agent_charlie",
        slot_idx=3,
        display_name="Charlie",
        dynasty_surname="Wilder",
        gender="BOY",
        stage="ADULT",
        credits=10.0,
    )
    p_wild = ParcelRecord(
        parcel_id="200_200",
        cx=200,
        cz=200,
        owner_id="agent_charlie",
        settlement_id=None,
        assessed_value=100.0,
    )
    prop_mgr.register_parcel(p_wild)

    results3 = prop_mgr.execute_probate_and_escheatment(
        deceased=charlie, all_agents={"agent_charlie": charlie}
    )
    assert len(results3) == 1
    assert results3[0] == ("200_200", "ESCHEATMENT_WILDERNESS", "UNCLAIMED")
    assert prop_mgr.parcels["200_200"].owner_id is None


def test_probate_and_escheatment_to_market(engine: SimulationEngine) -> None:
    """Verifies that when a homeowner dies without heirs, property is listed for sale."""
    # Spawn citizen who buys house
    citizen = engine.spawn_agent(race="HUMAN", gender="BOY", stage="ADULT", initial_credits=1000.0)
    for b in engine.city_layout.buildings.values():
        if b.for_sale:
            ok, _ = engine.city_layout.buy_building(b.building_id, citizen, bank=engine.bank)
            if ok:
                break

    assert citizen.home_building_id is not None
    house_id = citizen.home_building_id
    house = engine.city_layout.buildings[house_id]
    assert house.owner_id == citizen.agent_id
    assert house.for_sale is False

    # Simulate death of citizen with no spouse/parents/children
    citizen.spouse_id = None
    citizen.parent_ids = []
    engine.despawn_agent(citizen.agent_id, reason="NATURAL_DEATH")

    # Verify house is escheated to market: for_sale=True, owner_id=None
    assert house.for_sale is True
    assert house.owner_id is None
    assert house.owner_name is None


def test_multi_parcel_probate_and_sellerless_rejections(engine: SimulationEngine) -> None:
    """
    Verifies:
    1. Multi-parcel probate credits deceased balance once to treasury without duplication.
    2. Wilderness probate fallback transfers balance to bank reserve (DEF-04).
    3. Rejection of bankless/sellerless purchases for parcels and buildings (DEF-05 & DEF-08).
    """
    bank = engine.bank
    prop_mgr = engine.property_mgr

    # 1. Multi-parcel probate
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
    # Exactly 250.0 credited once, not duplicated
    assert engine.political_engine.polities["sylvanor"].treasury_credits == treasury_before + 250.0

    # 2. DEF-04: Wilderness escheatment fallback transfers remaining credits to bank reserve
    hermit = engine.spawn_agent(race="HUMAN", gender="BOY", stage="ADULT", initial_credits=180.0)
    hermit.alive = False
    p_wild = ParcelRecord(
        parcel_id="999_999",
        cx=999,
        cz=999,
        settlement_id=None,
        owner_id=hermit.agent_id,
        owner_type="INDIVIDUAL",
        assessed_value=50.0,
    )
    prop_mgr.register_parcel(p_wild)
    bank_res_before = bank.reserve_credits
    prop_mgr.execute_probate_and_escheatment(
        deceased=hermit, all_agents=engine.agents, settlement_treasury_credit_fn=None, bank=bank
    )
    assert hermit.credits == 0.0
    assert bank.reserve_credits == bank_res_before + 180.0

    # 3. DEF-05 & DEF-08: Rejection of bankless/sellerless purchases
    buyer = engine.spawn_agent(race="HUMAN", gender="GIRL", stage="ADULT", initial_credits=500.0)
    ok_p, err_p = prop_mgr.buy_parcel(buyer=buyer, parcel_id="999_999", bank=None, seller=None)
    assert not ok_p
    assert err_p == "BANK_OR_SELLER_REQUIRED"

    dummy_layout = CityLayoutEngine(engine=None)
    dummy_bld = BuildingRecord(
        building_id="bld_dummy",
        city_id="aurelia",
        building_type="HOUSE_T1_COTTAGE",
        racial_style="HUMAN",
        x=0.0,
        y=0.0,
        z=0.0,
        rotation_y=0.0,
        parcel_x=0,
        parcel_z=0,
        footprint_radius=8.0,
        owner_id=None,
        owner_name=None,
        for_sale=True,
        sale_price=50.0,
    )
    dummy_layout.buildings[dummy_bld.building_id] = dummy_bld
    dummy_buyer = engine.spawn_agent(
        race="HUMAN", gender="BOY", stage="ADULT", initial_credits=100.0
    )
    ok_b2, err_b2 = dummy_layout.buy_building("bld_dummy", dummy_buyer, bank=None)
    assert not ok_b2
    assert err_b2 == "BANK_OR_SELLER_REQUIRED"


def test_unified_4_tier_probate_parcel_and_building_sync(engine: SimulationEngine) -> None:
    """
    DEF-T2-03: Verifies that deceased homeowner with only a living mother/sibling
    transfers BOTH the deeded parcel AND occupying BuildingRecord to that relative,
    preventing building confiscation or auctions to strangers.
    """
    mother = engine.spawn_agent(race="HUMAN", gender="GIRL", stage="ADULT")
    son = engine.spawn_agent(race="HUMAN", gender="BOY", stage="ADULT")
    son.parent_ids = [mother.agent_id]
    son.credits = 50.0

    parcel = ParcelRecord(
        parcel_id="20_20", cx=20, cz=20, owner_id=son.agent_id, owner_type="INDIVIDUAL"
    )
    engine.property_mgr.register_parcel(parcel)

    building = BuildingRecord(
        building_id="bld_house_20_20",
        city_id="city_human",
        building_type="HOUSE_T1_COTTAGE",
        racial_style="HUMAN",
        x=320.0,
        y=10.0,
        z=320.0,
        rotation_y=0.0,
        parcel_x=20,
        parcel_z=20,
        owner_id=son.agent_id,
        owner_name=son.display_name,
        for_sale=False,
    )
    engine.city_layout.buildings["bld_house_20_20"] = building
    son.home_building_id = building.building_id

    # Son dies
    engine.despawn_agent(son.agent_id, reason="NATURAL_DEATH")

    # Mother must inherit parcel AND building
    assert parcel.owner_id == mother.agent_id
    assert building.owner_id == mother.agent_id
    assert not building.for_sale
    assert mother.home_building_id == building.building_id
    assert mother.credits == 60.0  # 10 initial + 50 inherited
