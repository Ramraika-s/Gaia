"""
tests/test_housing_gear_frontier_and_harvester.py
Verification suite for Gaia v4.0 Sprint 6:
- Live Housing Market & Closed-Loop Tier Upgrades
- Deceased Homeowner Probate & Escheatment
- Emergent Ring 2 Frontier Pioneer Settlements & Village Formation
- Modular Outfits, Accessories, Tools & Lanterns Economy
- Sandboxed Celestial Lore Harvester & Anachronism Rejection
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from scripts.celestial_ingest import run_ingest
from sim_core.bridge.mock_adapter import MockWorldAdapter
from sim_core.engine import SimulationEngine
from sim_core.schemas import AgentRecord, BuildingRecord, Vec3


@pytest.fixture
def test_engine() -> SimulationEngine:
    """Creates a clean headless SimulationEngine instance."""
    adapter = MockWorldAdapter()
    engine = SimulationEngine(adapter=adapter)
    return engine


def test_housing_market_double_entry_credit_conservation(test_engine: SimulationEngine):
    """Verifies that home purchases conserve credits with exactly 0.000000 drift."""
    engine = test_engine
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


def test_in_place_housing_tier_upgrades(test_engine: SimulationEngine):
    """Verifies that homeowners can upgrade cottages in-place (T1 -> T2 -> T3)."""
    engine = test_engine
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
        e["type"] == "HOUSE_UPGRADED" and e["new_tier"] == "HOUSE_T2_TOWNHOUSE"
        for e in events
    )
    assert cottage.building_type == "HOUSE_T2_TOWNHOUSE"
    assert cottage.footprint_radius == 11.0

    # Step market again -> homeowner still has credits >= 360, triggers T2 -> T3 upgrade
    events2 = housing.step_housing_market(engine.agents, bank, current_tick=21)
    assert any(
        e["type"] == "HOUSE_UPGRADED" and e["new_tier"] == "HOUSE_T3_MANOR"
        for e in events2
    )
    assert cottage.building_type == "HOUSE_T3_MANOR"
    assert cottage.footprint_radius == 14.0

    final_total = bank.reserve_credits + sum(a.credits for a in engine.agents.values())
    assert abs(final_total - initial_total) < 1e-6, "Credit drift detected in tier upgrades"


def test_probate_and_escheatment_to_market(test_engine: SimulationEngine):
    """Verifies that deceased homeowners' properties inherit or escheat back to market."""
    engine = test_engine
    bank = engine.bank
    housing = engine.housing_market

    # Deceased homeowner with child
    deceased = AgentRecord(
        agent_id="deceased_parent",
        slot_idx=2,
        race="HUMAN",
        gender="BOY",
        stage="ADULT",
        age_ticks=8000,
        display_name="Marcus",
        dynasty_surname="Oldstone",
        pos=Vec3(x=355.0, y=10.0, z=1090.0),
        credits=50.0,
        alive=False,  # Dead
    )
    heir = AgentRecord(
        agent_id="living_child",
        slot_idx=3,
        race="HUMAN",
        gender="GIRL",
        stage="ADULT",
        age_ticks=3000,
        display_name="Sylvia",
        dynasty_surname="Oldstone",
        parent_ids=["deceased_parent"],
        pos=Vec3(x=355.0, y=10.0, z=1090.0),
        credits=100.0,
        alive=True,
    )
    engine.agents[deceased.agent_id] = deceased
    engine.agents[heir.agent_id] = heir

    house = list(engine.city_layout.buildings.values())[5]
    house.owner_id = deceased.agent_id
    house.owner_name = "Marcus Oldstone"
    house.for_sale = False

    events = housing.step_housing_market(engine.agents, bank, current_tick=30)
    assert any(
        e["type"] == "HOUSE_PROBATE_INHERITED" and e["heir_id"] == heir.agent_id
        for e in events
    )
    assert house.owner_id == heir.agent_id
    assert heir.home_building_id == house.building_id

    # Now make heir dead too with no remaining heirs -> escheatment to market
    heir.alive = False
    events2 = housing.step_housing_market(engine.agents, bank, current_tick=31)
    assert any(e["type"] == "HOUSE_ESCHEATMENT_FOR_SALE" for e in events2)
    assert house.owner_id is None
    assert house.for_sale is True


def test_ring_2_frontier_pioneers_and_village_clustering(test_engine: SimulationEngine):
    """Verifies that pioneers claim Ring 2 plots on dry land and cluster into villages."""
    engine = test_engine
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
    r = (pioneer_bld.x ** 2 + pioneer_bld.z ** 2) ** 0.5
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
        x=2000.0, y=15.0, z=500.0,
        rotation_y=0.0, parcel_x=125, parcel_z=31,
        owner_id="pioneer_1", owner_name="Grim Wildstrider",
        is_frontier=True,
    )
    bld_b = BuildingRecord(
        building_id="bld_frontier_c2",
        city_id="frontier",
        building_type="HOUSE_T1_COTTAGE",
        racial_style="BEASTHUMAN",
        x=2020.0, y=15.0, z=510.0,
        rotation_y=0.0, parcel_x=126, parcel_z=31,
        owner_id="pioneer_2", owner_name="Kira Wildstrider",
        is_frontier=True,
    )
    bld_c = BuildingRecord(
        building_id="bld_frontier_c3",
        city_id="frontier",
        building_type="HOUSE_T1_COTTAGE",
        racial_style="BEASTHUMAN",
        x=2010.0, y=15.0, z=530.0,
        rotation_y=0.0, parcel_x=125, parcel_z=33,
        owner_id="pioneer_3", owner_name="Boran Wildstrider",
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


def test_gear_economy_crafting_and_profession_equipping(test_engine: SimulationEngine):
    """Verifies gear crafting, autonomous purchase, and profession-matched equipping."""
    engine = test_engine
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

    # Step gear economy: smith crafts items, knight buys sword/plate, farmer buys hoe/tunic
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


def test_celestial_lore_harvester_offline_and_anachronism_rejection():
    """Verifies that celestial_ingest parses lore and rejects anachronisms."""
    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "celestial_metallurgy.md"
        output_file = Path(tmpdir) / "pack_craft.json"

        # Content with fantasy lore and a modern term that must be cleansed
        input_file.write_text(
            """# The Sacred Crucible of Aethelgard

Ancient smiths learned that tempering sky-iron under moonlight grants weapons sharpness.
By folding the ore seven times in dragon flame, the steel resists corrosion and absorbs shock.
The craftsmen spoke through an internet of whispers and used a computer of stars for ratios.

## Techniques of the Deep Forge

Deep in the obsidian caves, dwarven masters blend volcanic sulfur with mithril ingots.
This union produces armor impenetrable by mundane arrows, radiating a faint azure glow.
""",
            encoding="utf-8",
        )

        pack = run_ingest(
            input_path=input_file,
            subject="craft_and_metallurgy",
            output_path=output_file,
            use_llm=False,
            max_entries=5,
            era_tier=2,
            author="Master Vane",
        )

        assert len(pack.entries) >= 1
        assert pack.entries[0].subject == "craft_and_metallurgy"
        assert output_file.exists()

        # Check that no modern forbidden terms survived
        for entry in pack.entries:
            assert "internet" not in entry.body.lower()
            assert "computer" not in entry.body.lower()
            assert len(entry.entry_id) >= 4
            assert len(entry.fact_key.split(".")) == 3
            assert entry.era_tier == 2
            assert entry.author == "Master Vane"
