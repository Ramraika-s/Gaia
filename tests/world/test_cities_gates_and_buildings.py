# tests/world/test_cities_gates_and_buildings.py
from __future__ import annotations

import json
import math
import socket
from pathlib import Path

import pytest
import websockets

from scripts.launch_gaia import spawn_initial_population
from sim_core.bridge.godot_ws_bridge import GodotWebSocketBridge
from sim_core.engine import SimulationEngine
from sim_core.schemas import AgentRecord, Vec3
from sim_core.world.city_layout import RING_1_CITY_SPECS, CityLayoutEngine


def get_free_port() -> int:
    """Finds an available TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_five_cities_geometry_palaces_and_gates(tmp_path: Path) -> None:
    """Verifies all 5 cities exist at r=1,150m with 72° spacing, palaces, 4 gates, and deeds."""
    engine = SimulationEngine(
        db_path=tmp_path / "test_cities.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        headless=True,
    )
    city_mgr = engine.city_layout

    assert len(city_mgr.cities) == 5
    expected_cities = {"sylvanor", "aurelia", "fenris_hold", "malakor", "drakonis_spire"}
    assert set(city_mgr.cities.keys()) == expected_cities

    for cid, spec in RING_1_CITY_SPECS.items():
        city = city_mgr.cities[cid]
        assert city.name == spec["name"]
        assert city.native_race == spec["native_race"]
        assert city.racial_style == spec["racial_style"]
        assert city.godmother_slot == spec["godmother_slot"]
        assert city.curtain_wall_radius == 240.0

        dist_origin = math.hypot(city.center_x, city.center_z)
        assert abs(dist_origin - 1150.0) < 5.0, f"City {cid} dist {dist_origin} not ~1150m"

        palace_id = f"bld_{cid}_palace"
        assert palace_id in city_mgr.buildings
        palace = city_mgr.buildings[palace_id]
        assert palace.building_type == "GODMOTHER_PALACE"
        assert palace.racial_style == city.racial_style
        assert palace.footprint_radius >= 25.0
        assert not palace.for_sale

        parcel_id = f"{palace.parcel_x}_{palace.parcel_z}"
        assert parcel_id in engine.property_mgr.parcels
        parcel = engine.property_mgr.parcels[parcel_id]
        assert parcel.settlement_id == cid

        main_angle = math.atan2(-city.center_z, -city.center_x)
        gate_specs = [
            ("gate_imperial", main_angle),
            ("gate_right", (main_angle + math.pi * 0.5) % (2.0 * math.pi)),
            ("gate_outer", (main_angle + math.pi) % (2.0 * math.pi)),
            ("gate_left", (main_angle + math.pi * 1.5) % (2.0 * math.pi)),
        ]
        for g_suf, g_angle in gate_specs:
            gid = f"bld_{cid}_{g_suf}"
            assert gid in city_mgr.buildings
            gate = city_mgr.buildings[gid]
            assert gate.building_type == "CITY_GATE"
            dist_to_center = math.hypot(gate.x - city.center_x, gate.z - city.center_z)
            assert abs(dist_to_center - 240.0) < 2.0
            expected_rot_y = round((math.pi * 0.5) - g_angle, 4)
            assert gate.rotation_y == expected_rot_y
            assert abs(math.sin(gate.rotation_y) - math.cos(g_angle)) < 1e-3
            assert abs(math.cos(gate.rotation_y) - math.sin(g_angle)) < 1e-3

        seed_buildings = [
            b
            for b in city_mgr.buildings.values()
            if b.city_id == cid and b.building_type not in ("GODMOTHER_PALACE", "CITY_GATE")
        ]
        assert len(seed_buildings) == 44

        unique_parcels = {(b.parcel_x, b.parcel_z) for b in seed_buildings}
        assert len(unique_parcels) == 44
        for i, b1 in enumerate(seed_buildings):
            dist_from_city = math.hypot(b1.x - city.center_x, b1.z - city.center_z)
            assert 58.0 <= dist_from_city <= 214.0
            for b2 in seed_buildings[i + 1 :]:
                pair_dist = math.hypot(b1.x - b2.x, b1.z - b2.z)
                assert pair_dist >= b1.footprint_radius + b2.footprint_radius + 2.5

        btypes = {b.building_type for b in seed_buildings}
        assert "HOUSE_T1_COTTAGE" in btypes
        assert "HOUSE_T2_TOWNHOUSE" in btypes
        assert "HOUSE_T3_MANOR" in btypes
        assert any("SHOP_" in bt for bt in btypes)

        for_sale_count = sum(1 for b in seed_buildings if b.for_sale)
        owned_count = sum(1 for b in seed_buildings if not b.for_sale)
        assert for_sale_count >= 14
        assert owned_count >= 26


def test_ring_2_frontier_wilderness_invariant() -> None:
    """Asserts Ring 2 (1,500m - 3,300m) is completely pristine with zero pre-built buildings."""
    layout = CityLayoutEngine()
    passed, msg = layout.verify_ring_2_wilderness()
    assert passed, msg

    for b in layout.buildings.values():
        dist_origin = math.hypot(b.x, b.z)
        assert not (1500.0 <= dist_origin <= 3300.0)


def test_city_guard_patrols_and_gate_watches(engine: SimulationEngine) -> None:
    """Verifies city guard garrisons are spawned and patrol gates/walls."""
    city_mgr = engine.city_layout

    elf_guards = city_mgr.spawn_city_guard_garrison(engine.agents, "sylvanor", count=10)
    assert len(elf_guards) == 10
    for g in elf_guards:
        assert g.role == "CITY_GUARD"
        assert g.race == "ELF"
        assert g.alive

    for t in range(250):
        city_mgr.step_patrols(t, engine.agents)

    dist_to_center = math.hypot(
        elf_guards[0].pos.x - city_mgr.cities["sylvanor"].center_x,
        elf_guards[0].pos.z - city_mgr.cities["sylvanor"].center_z,
    )
    assert 220.0 <= dist_to_center <= 250.0


def test_predominant_racial_demographics(tmp_path: Path) -> None:
    """Verifies that each city is populated >= 75% by its native race."""
    engine = SimulationEngine(
        db_path=tmp_path / "test_demo.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        headless=True,
    )

    spawn_initial_population(engine, num_agents=600)
    assert len(engine.agents) >= 500

    for cid, city in engine.city_layout.cities.items():
        city_agents = [
            a
            for a in engine.agents.values()
            if a.role != "PALACE_KNIGHT"
            and math.hypot(a.pos.x - city.center_x, a.pos.z - city.center_z) <= 260.0
        ]
        assert len(city_agents) >= 30

        native_count = sum(1 for a in city_agents if a.race == city.native_race)
        native_pct = (native_count / float(len(city_agents))) * 100.0
        assert native_pct >= 75.0, f"City {cid} native pct was {native_pct:.1f}%, expected >= 75.0%"


@pytest.mark.asyncio
async def test_websocket_building_sync_and_live_purchase(tmp_path: Path) -> None:
    """
    Tests that:
    1. Real WebSocket connection delivers BUILDING_SYNC on CLIENT_HANDSHAKE.
    2. Buying a house debits credits, changes ownership, updates parcel deed, and
       broadcasts live BUILDING_UPDATE to clients.
    """
    port = get_free_port()
    engine = SimulationEngine(
        db_path=tmp_path / "test_ws.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        headless=True,
    )
    bridge = GodotWebSocketBridge(host="127.0.0.1", port=port, engine=engine)
    engine.adapter = bridge

    await bridge.start_server_async()
    try:
        uri = f"ws://127.0.0.1:{port}"
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({"type": "CLIENT_HANDSHAKE", "client_version": "4.7.2"}))

            ack = json.loads(await ws.recv())
            assert ack["type"] == "HANDSHAKE_ACK"

            book_sync = json.loads(await ws.recv())
            assert book_sync["type"] == "BOOK_STATE_SYNC"

            bld_sync = json.loads(await ws.recv())
            assert bld_sync["type"] == "BUILDING_SYNC"
            assert len(bld_sync["cities"]) == 5
            assert len(bld_sync["buildings"]) == 245

            for_sale_bld = next(b for b in engine.city_layout.buildings.values() if b.for_sale)
            bld_id = for_sale_bld.building_id
            sale_price = for_sale_bld.sale_price

            buyer = AgentRecord(
                agent_id="buyer_adventurer_01",
                slot_idx=0,
                display_name="Elidor Swiftarrow",
                dynasty_surname="Swiftarrow",
                gender="BOY",
                race="ELF",
                credits=1000.0,
                pos=Vec3(x=0.0, y=0.0, z=0.0),
            )
            engine.agents[buyer.agent_id] = buyer

            success, msg = engine.buy_building(bld_id, buyer)
            assert success, msg
            assert buyer.credits == 1000.0 - sale_price
            assert not for_sale_bld.for_sale
            assert for_sale_bld.owner_id == buyer.agent_id
            assert for_sale_bld.owner_name == buyer.display_name

            parcel_id = f"{for_sale_bld.parcel_x}_{for_sale_bld.parcel_z}"
            parcel = engine.property_mgr.parcels[parcel_id]
            assert parcel.owner_id == buyer.agent_id
            assert parcel.for_sale_price is None

            update_frame = json.loads(await ws.recv())
            assert update_frame["type"] == "BUILDING_UPDATE"
            assert update_frame["building"]["building_id"] == bld_id
            assert update_frame["building"]["for_sale"] is False
            assert update_frame["building"]["owner_id"] == buyer.agent_id

    finally:
        await bridge.stop_server_async()
