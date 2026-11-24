# tests/persistence/test_restore_rewind_and_launcher.py
from __future__ import annotations

import argparse
import asyncio
import shutil
import socket
from pathlib import Path

import pytest

from scripts.launch_gaia import GaiaLauncher
from sim_core.brains.personality import MoodState, PersonalityVector
from sim_core.bridge.godot_ws_bridge import GodotWebSocketBridge
from sim_core.engine import SimulationEngine
from sim_core.god_console.cli import RichGodConsole
from sim_core.schemas import AgentRecord, BuildingRecord, Vec3, WorldLibraryEntry


def get_ephemeral_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.slow
def test_full_save_and_boot_restore_roundtrip(tmp_path: Path) -> None:
    db_path = tmp_path / "civilization.db"
    checkpoints_dir = tmp_path / "checkpoints"
    god_ledger_dir = tmp_path / "god_ledger"

    engine = SimulationEngine(
        db_path=db_path,
        checkpoints_dir=checkpoints_dir,
        god_ledger_dir=god_ledger_dir,
        headless=True,
    )

    ag1 = AgentRecord(
        agent_id="agent_smith_01",
        slot_idx=0,
        display_name="Vulcan",
        dynasty_surname="Forgeborn",
        race="HUMAN",
        gender="BOY",
        role="MERCHANT",
        title="Master Smith",
        profession="BLACKSMITH",
        profession_level=4,
        profession_xp=320.5,
        hygiene=0.88,
        fatigue=0.15,
        yaw=1.5708,
        pos=Vec3(x=120.0, y=10.0, z=140.0),
        credits=350.0,
        known_books=["metallurgy_vol_1"],
        personality=PersonalityVector(courage=0.85, curiosity=0.75),
        mood=MoodState(calm=0.9, inspired=0.7),
        equipped_gear=["Masterwork Hammer"],
        home_building_id="bld_solaria_forge_01",
    )
    ag2 = AgentRecord(
        agent_id="agent_scholar_02",
        slot_idx=1,
        display_name="Athena",
        dynasty_surname="Owl",
        race="ELF",
        gender="GIRL",
        role="SCHOLAR",
        title="High Arcanist",
        profession="ALCHEMIST",
        profession_level=3,
        profession_xp=180.0,
        hygiene=0.95,
        fatigue=0.20,
        yaw=3.1415,
        pos=Vec3(x=-200.0, y=5.0, z=-150.0),
        credits=250.0,
        known_books=["herbalism_vol_2"],
        personality=PersonalityVector(courage=0.4, curiosity=0.95),
        mood=MoodState(calm=0.8, inspired=0.85),
        equipped_gear=[],
        home_building_id=None,
    )
    engine.agents = {ag1.agent_id: ag1, ag2.agent_id: ag2}
    engine.spatial_grid.update_agent(ag1.agent_id, ag1.pos.x, ag1.pos.z)
    engine.spatial_grid.update_agent(ag2.agent_id, ag2.pos.x, ag2.pos.z)

    bld1 = BuildingRecord(
        building_id="bld_solaria_forge_01",
        city_id="solaria",
        building_type="SHOP_BLACKSMITH",
        racial_style="HUMAN",
        x=120.0,
        y=10.0,
        z=140.0,
        rotation_y=0.0,
        parcel_x=7,
        parcel_z=8,
        footprint_radius=8.0,
        owner_id=ag1.agent_id,
        owner_name=ag1.display_name,
        is_frontier=False,
    )
    bld2 = BuildingRecord(
        building_id="bld_frontier_homestead_01",
        city_id="",
        building_type="HOUSE_T1_COTTAGE",
        racial_style="ELF",
        x=2400.0,
        y=12.0,
        z=1800.0,
        rotation_y=0.0,
        parcel_x=150,
        parcel_z=112,
        footprint_radius=6.0,
        settlement_id="frontier_solaria",
        is_frontier=True,
    )
    engine.city_layout.buildings[bld1.building_id] = bld1
    engine.housing_market.frontier_buildings[bld2.building_id] = bld2
    engine.housing_market.pioneer_count = 1
    engine.navigation.register_building_footprint(
        name=bld1.building_id,
        cx=bld1.x,
        cz=bld1.z,
        radius=bld1.footprint_radius,
        door_x=bld1.x,
        door_z=bld1.z + bld1.footprint_radius,
        building_type=bld1.building_type,
    )
    engine.navigation.register_building_footprint(
        name=bld2.building_id,
        cx=bld2.x,
        cz=bld2.z,
        radius=bld2.footprint_radius,
        door_x=bld2.x,
        door_z=bld2.z + bld2.footprint_radius,
        building_type=bld2.building_type,
    )

    lib_entry = WorldLibraryEntry(
        entry_id="metallurgy_vol_1",
        topic="metallurgy",
        title="Principles of Blast Furnace Forging",
        summary="Foundational guide to high-temperature iron purification.",
        author_id=ag1.agent_id,
        created_tick=0,
        body="Step 1: Construct refractory clay lining. Step 2: Ensure continuous forced air.",
        subject="crafting",
        section="metallurgy",
        mechanical_effects={"forge_speed": 1.25},
    )
    engine.governance_engine.library_entries[lib_entry.entry_id] = lib_entry
    engine.governance_engine.live_engine_overrides["NON_AGGRESSION_COVENANT"] = False
    engine.governance_engine.live_engine_overrides["DIVINE_TRUCE_HOURS"] = 48.0

    engine.divine_hierarchy.entities["gm_human"].bestowed_name = "Lady_Astraea"
    engine.divine_autonomy.deities["gm_human"].name = "Lady_Astraea"

    engine.bank.reserve_credits = 49400.0
    total_pre_credits = engine.bank.reserve_credits + sum(a.credits for a in engine.agents.values())
    assert abs(total_pre_credits - 50000.0) < 1e-6
    initial_cap = engine.batched_net.capacity

    manifest = engine.commit_end_of_day(advance_day=True)
    assert manifest.status == "VERIFIED"
    assert manifest.day == 1

    engine_restored = SimulationEngine(
        db_path=db_path,
        checkpoints_dir=checkpoints_dir,
        god_ledger_dir=god_ledger_dir,
        headless=True,
    )
    assert engine_restored.has_verified_checkpoint()

    day_res, man_res, status_msg = engine_restored.restore_from_checkpoint()
    assert day_res == 1
    assert man_res.day == 1
    assert "Verified" in status_msg or "BOOT_CLEAN" in status_msg

    assert engine_restored.current_day == 2

    total_post_credits = engine_restored.bank.reserve_credits + sum(
        a.credits for a in engine_restored.agents.values()
    )
    assert abs(total_pre_credits - total_post_credits) < 1e-6

    assert len(engine_restored.agents) == 2
    res_ag1 = engine_restored.agents["agent_smith_01"]
    assert res_ag1.display_name == "Vulcan"
    assert res_ag1.role == "MERCHANT"
    assert res_ag1.title == "Master Smith"
    assert res_ag1.profession == "BLACKSMITH"
    assert res_ag1.profession_level == 4
    assert abs(res_ag1.profession_xp - 320.5) < 1e-5
    assert abs(res_ag1.hygiene - 0.88) < 1e-5
    assert abs(res_ag1.fatigue - 0.15) < 1e-5
    assert abs(res_ag1.yaw - 1.5708) < 1e-4
    assert res_ag1.pos.x == 120.0 and res_ag1.pos.z == 140.0
    assert res_ag1.known_books == ["metallurgy_vol_1"]
    assert res_ag1.personality is not None
    assert abs(res_ag1.personality.courage - 0.85) < 1e-5
    assert res_ag1.mood is not None
    assert abs(res_ag1.mood.calm - 0.9) < 1e-5
    assert len(res_ag1.equipped_gear) == 1
    assert res_ag1.equipped_gear[0] == "Masterwork Hammer"
    assert res_ag1.home_building_id == "bld_solaria_forge_01"

    assert "bld_solaria_forge_01" in engine_restored.city_layout.buildings
    assert "bld_frontier_homestead_01" in engine_restored.housing_market.frontier_buildings
    assert engine_restored.housing_market.pioneer_count == 1
    frontier_bld = engine_restored.housing_market.frontier_buildings["bld_frontier_homestead_01"]
    assert frontier_bld.is_frontier is True
    assert frontier_bld.settlement_id == "frontier_solaria"

    assert "metallurgy_vol_1" in engine_restored.governance_engine.library_entries
    restored_book = engine_restored.governance_engine.library_entries["metallurgy_vol_1"]
    assert restored_book.body is not None
    assert "Step 1: Construct refractory clay lining." in restored_book.body
    overrides = engine_restored.governance_engine.live_engine_overrides
    assert overrides["NON_AGGRESSION_COVENANT"] is False
    assert overrides["DIVINE_TRUCE_HOURS"] == 48.0

    human_gm = engine_restored.divine_hierarchy.entities["gm_human"]
    assert human_gm.bestowed_name == "Lady_Astraea"
    assert engine_restored.divine_autonomy.deities["gm_human"].name == "Lady_Astraea"
    assert engine_restored.batched_net.capacity == initial_cap


@pytest.mark.slow
def test_historical_rewind(tmp_path: Path) -> None:
    db_path = tmp_path / "civ_rewind.db"
    checkpoints_dir = tmp_path / "checkpoints"
    god_ledger_dir = tmp_path / "god_ledger"

    engine = SimulationEngine(
        db_path=db_path,
        checkpoints_dir=checkpoints_dir,
        god_ledger_dir=god_ledger_dir,
        headless=True,
    )
    console = RichGodConsole(engine=engine)

    ag = AgentRecord(
        agent_id="timetraveler",
        slot_idx=0,
        display_name="Chronos",
        dynasty_surname="Aeon",
        race="HUMAN",
        gender="BOY",
        credits=100.0,
    )
    engine.agents = {ag.agent_id: ag}
    bld_day1 = BuildingRecord(
        building_id="house_d1",
        city_id="solaria",
        building_type="HOUSE_T1_COTTAGE",
        racial_style="HUMAN",
        x=50.0,
        y=0.0,
        z=50.0,
        rotation_y=0.0,
        parcel_x=3,
        parcel_z=3,
        owner_id=ag.agent_id,
        owner_name=ag.display_name,
        for_sale=False,
    )
    engine.city_layout.buildings = {bld_day1.building_id: bld_day1}
    engine.commit_end_of_day(advance_day=True)
    assert engine.current_day == 2

    engine.agents["timetraveler"].credits = 250.0
    bld_day2 = BuildingRecord(
        building_id="house_d2",
        city_id="solaria",
        building_type="HOUSE_T2_TOWNHOUSE",
        racial_style="HUMAN",
        x=60.0,
        y=0.0,
        z=60.0,
        rotation_y=0.0,
        parcel_x=3,
        parcel_z=4,
        owner_id=ag.agent_id,
        owner_name=ag.display_name,
        for_sale=False,
    )
    engine.city_layout.buildings["house_d2"] = bld_day2
    engine.commit_end_of_day(advance_day=True)
    assert engine.current_day == 3

    engine.agents["timetraveler"].credits = 999.0
    engine.commit_end_of_day(advance_day=True)
    assert engine.current_day == 4

    rewind_out = console.execute_command("rewind 2")
    assert "REWIND_SUCCESS" in rewind_out or "Successfully rewound" in rewind_out
    assert engine.current_day == 3

    assert len(engine.agents) == 1
    assert abs(engine.agents["timetraveler"].credits - 250.0) < 1e-4

    assert len(engine.city_layout.buildings) == 2
    assert "house_d1" in engine.city_layout.buildings
    assert "house_d2" in engine.city_layout.buildings

    invalid_rewind = console.execute_command("rewind 99")
    assert "Cannot rewind" in invalid_rewind or "not found" in invalid_rewind
    assert engine.current_day == 3


@pytest.mark.slow
def test_rewind_adversarial_continuity(tmp_path: Path) -> None:
    db_path = tmp_path / "civ_adv_rewind.db"
    checkpoints_dir = tmp_path / "checkpoints"
    god_ledger_dir = tmp_path / "god_ledger"

    bridge = GodotWebSocketBridge(host="127.0.0.1", port=18765, initial_capacity=2048)
    engine = SimulationEngine(
        db_path=db_path,
        checkpoints_dir=checkpoints_dir,
        god_ledger_dir=god_ledger_dir,
        adapter=bridge,
        headless=True,
    )
    bridge.engine = engine
    console = RichGodConsole(engine=engine)

    # Day 1: Palace Knight, City Guard, citizen, building
    knight = AgentRecord(
        agent_id="knight_01",
        slot_idx=0,
        display_name="Galahad",
        dynasty_surname="Sunshield",
        race="HUMAN",
        gender="BOY",
        role="PALACE_KNIGHT",
        pos=Vec3(x=0.0, y=0.0, z=0.0),
        credits=200.0,
    )
    guard = AgentRecord(
        agent_id="guard_aurelia_01",
        slot_idx=1,
        display_name="Marcus",
        dynasty_surname="Watch",
        race="HUMAN",
        gender="BOY",
        role="CITY_GUARD",
        settlement_id="aurelia",
        pos=Vec3(x=50.0, y=0.0, z=50.0),
        credits=150.0,
    )
    citizen_d1 = AgentRecord(
        agent_id="citizen_d1",
        slot_idx=2,
        display_name="Civic",
        dynasty_surname="Citizen",
        race="ELF",
        gender="GIRL",
        role="CITIZEN",
        pos=Vec3(x=30.0, y=0.0, z=30.0),
        credits=300.0,
    )
    engine.agents = {
        knight.agent_id: knight,
        guard.agent_id: guard,
        citizen_d1.agent_id: citizen_d1,
    }
    for ag in engine.agents.values():
        engine.spatial_grid.update_agent(ag.agent_id, ag.pos.x, ag.pos.z)
        bridge.spawn_agent(ag.agent_id, ag.slot_idx, ag.model_dump())

    bld_d1 = BuildingRecord(
        building_id="bld_d1",
        city_id="aurelia",
        building_type="SHOP_BLACKSMITH",
        racial_style="HUMAN",
        x=20.0,
        y=0.0,
        z=20.0,
        rotation_y=0.0,
        parcel_x=1,
        parcel_z=1,
    )
    engine.city_layout.buildings[bld_d1.building_id] = bld_d1
    engine.navigation.register_building_footprint(
        name=bld_d1.building_id,
        cx=bld_d1.x,
        cz=bld_d1.z,
        radius=bld_d1.footprint_radius,
        door_x=bld_d1.x,
        door_z=bld_d1.z + 8.0,
        building_type=bld_d1.building_type,
    )

    engine.wtc.current_prices["GRAIN"] = 12.50
    engine.bank.reserve_credits = 49350.0
    total_d1_credits = engine.bank.reserve_credits + sum(a.credits for a in engine.agents.values())
    assert abs(total_d1_credits - 50000.0) < 1e-6

    engine.commit_end_of_day(advance_day=True)
    assert engine.current_day == 2

    citizen_d2 = AgentRecord(
        agent_id="citizen_d2",
        slot_idx=3,
        display_name="Newcomer",
        dynasty_surname="Ghost",
        race="DEMON",
        gender="BOY",
        role="CITIZEN",
        pos=Vec3(x=2000.0, y=0.0, z=2000.0),
        credits=50.0,
    )
    engine.agents[citizen_d2.agent_id] = citizen_d2
    engine.spatial_grid.update_agent(citizen_d2.agent_id, citizen_d2.pos.x, citizen_d2.pos.z)
    bridge.spawn_agent(citizen_d2.agent_id, citizen_d2.slot_idx, citizen_d2.model_dump())

    bld_pioneer_d2 = BuildingRecord(
        building_id="bld_pioneer_d2",
        city_id="",
        building_type="HOUSE_T1_COTTAGE",
        racial_style="DEMON",
        x=2200.0,
        y=0.0,
        z=2200.0,
        rotation_y=0.0,
        parcel_x=137,
        parcel_z=137,
        settlement_id="frontier_ashlands",
        is_frontier=True,
    )
    engine.city_layout.buildings[bld_pioneer_d2.building_id] = bld_pioneer_d2
    engine.housing_market.frontier_buildings[bld_pioneer_d2.building_id] = bld_pioneer_d2
    engine.navigation.register_building_footprint(
        name=bld_pioneer_d2.building_id,
        cx=bld_pioneer_d2.x,
        cz=bld_pioneer_d2.z,
        radius=bld_pioneer_d2.footprint_radius,
        door_x=bld_pioneer_d2.x,
        door_z=bld_pioneer_d2.z + 8.0,
        building_type=bld_pioneer_d2.building_type,
    )

    engine.wtc.current_prices["GRAIN"] = 25.00
    engine.bank.reserve_credits = 50000.0 - sum(a.credits for a in engine.agents.values())

    engine.commit_end_of_day(advance_day=True)
    assert engine.current_day == 3
    assert bool(bridge.active_mask[citizen_d2.slot_idx]) is True

    out = console.execute_command("rewind 1")
    assert "SUCCESS" in out or "Rewound" in out

    assert "citizen_d2" not in engine.agents
    assert citizen_d2.slot_idx not in bridge.slot_to_agent_id
    assert not bridge.active_mask[citizen_d2.slot_idx]

    assert "bld_pioneer_d2" not in engine.city_layout.buildings
    assert "bld_pioneer_d2" not in engine.housing_market.frontier_buildings
    footprint_names = [fp.name for fp in engine.navigation.footprints]
    assert "bld_pioneer_d2" not in footprint_names
    assert "Grand Divine Palace" in footprint_names
    assert "bld_d1" in footprint_names

    assert abs(engine.wtc.current_prices["GRAIN"] - 12.50) < 1e-4


@pytest.mark.slow
def test_same_day_manual_save_manifest_history(tmp_path: Path) -> None:
    import json

    db_path = tmp_path / "civ_same_day.db"
    checkpoints_dir = tmp_path / "checkpoints"
    god_ledger_dir = tmp_path / "god_ledger"

    engine = SimulationEngine(
        db_path=db_path,
        checkpoints_dir=checkpoints_dir,
        god_ledger_dir=god_ledger_dir,
        headless=True,
    )
    console = RichGodConsole(engine=engine)

    engine.commit_end_of_day(advance_day=True)
    assert engine.current_day == 2

    console.execute_command("save")
    engine.commit_end_of_day(advance_day=True)
    assert engine.current_day == 3

    history_file = checkpoints_dir / "manifest_history.json"
    with open(history_file, encoding="utf-8") as f:
        history = json.load(f)

    day_2_entries = [h for h in history if h.get("day") == 2]
    assert len(day_2_entries) == 1

    day2_db = checkpoints_dir / "day_00002.db"
    with open(day2_db, "wb") as f:
        f.write(b"CORRUPTED_GARBAGE_BYTES")

    engine_rewound = SimulationEngine(
        db_path=db_path,
        checkpoints_dir=checkpoints_dir,
        god_ledger_dir=god_ledger_dir,
        headless=True,
    )
    day_res, man_res, alert = engine_rewound.restore_from_checkpoint()
    assert day_res == 1
    assert "REWOUND" in alert or "Rewound" in alert or "CORRUPTION" in alert


@pytest.mark.slow
def test_launch_gaia_auto_restore_vs_fresh(tmp_path: Path) -> None:
    db_path = tmp_path / "launcher_civ.db"
    checkpoints_dir = tmp_path / "checkpoints"
    god_ledger_dir = tmp_path / "god_ledger"

    engine = SimulationEngine(
        db_path=db_path,
        checkpoints_dir=checkpoints_dir,
        god_ledger_dir=god_ledger_dir,
        headless=True,
    )
    ag = AgentRecord(
        agent_id="persisted_founder",
        slot_idx=0,
        display_name="Founder",
        dynasty_surname="Origin",
        race="HUMAN",
        gender="BOY",
        credits=500.0,
    )
    engine.agents = {ag.agent_id: ag}
    engine.commit_end_of_day(advance_day=True)

    # 1. Launcher with fresh=False should auto-restore checkpoint
    mock_args_restore = argparse.Namespace(
        agents=100,
        speed=1.0,
        headless=True,
        port=8765,
        host="127.0.0.1",
        db_path=db_path,
        checkpoints_dir=checkpoints_dir,
        god_ledger_dir=god_ledger_dir,
        terrain=None,
        duration_seconds=0,
        fresh=False,
        llm_model="Huihui-Qwen3.5-4B",
        llm_port=8080,
    )

    launcher_restore = GaiaLauncher(mock_args_restore)
    launcher_restore.engine = SimulationEngine(
        db_path=db_path,
        checkpoints_dir=checkpoints_dir,
        god_ledger_dir=god_ledger_dir,
        headless=True,
    )

    assert not launcher_restore.args.fresh and launcher_restore.engine.has_verified_checkpoint()
    day, man, msg = launcher_restore.engine.restore_from_checkpoint()
    assert day == 1
    assert "persisted_founder" in launcher_restore.engine.agents
    assert len(launcher_restore.engine.agents) == 1

    # 2. Launcher with fresh=True should wipe previous state and NOT restore
    assert db_path.exists()
    assert checkpoints_dir.exists()

    mock_args_fresh = argparse.Namespace(
        agents=100,
        speed=1.0,
        headless=True,
        port=8765,
        host="127.0.0.1",
        db_path=db_path,
        checkpoints_dir=checkpoints_dir,
        god_ledger_dir=god_ledger_dir,
        terrain=None,
        duration_seconds=0,
        fresh=True,
        llm_model="Huihui-Qwen3.5-4B",
        llm_port=8080,
    )
    launcher_fresh = GaiaLauncher(mock_args_fresh)

    if launcher_fresh.args.fresh:
        db_p = Path(launcher_fresh.args.db_path)
        if db_p.exists():
            db_p.unlink()
        for ext in ("-wal", "-shm"):
            wal_p = db_p.with_name(db_p.name + ext)
            if wal_p.exists():
                wal_p.unlink()
        cp_p = Path(launcher_fresh.args.checkpoints_dir)
        if cp_p.exists():
            shutil.rmtree(cp_p)
        gl_p = Path(launcher_fresh.args.god_ledger_dir)
        if gl_p.exists():
            shutil.rmtree(gl_p)

    assert not db_path.exists()
    assert not checkpoints_dir.exists()


@pytest.mark.asyncio
async def test_launcher_pause_and_courthouse_sign(tmp_path: Path) -> None:
    """Verifies simulation loop pauses when is_running is False without advancing ticks."""
    port = get_ephemeral_port()
    args = argparse.Namespace(
        agents=10,
        speed=1.0,
        port=port,
        host="127.0.0.1",
        headless=True,
        max_ticks=0,
        duration_seconds=0.0,
        db_path=str(tmp_path / "civilization.db"),
        checkpoints_dir=str(tmp_path / "checkpoints"),
        god_ledger_dir=str(tmp_path / "god_ledger"),
        heightmap_path="nonexistent.npy",
        llm=False,
        llm_model="none.gguf",
        llm_port=8080,
        llm_bin="none",
    )

    launcher = GaiaLauncher(args)
    capacity = 2048
    launcher.bridge = GodotWebSocketBridge(host=args.host, port=port, initial_capacity=capacity)
    launcher.engine = SimulationEngine(
        db_path=args.db_path,
        checkpoints_dir=args.checkpoints_dir,
        god_ledger_dir=args.god_ledger_dir,
        adapter=launcher.bridge,
        headless=True,
        initial_capacity=capacity,
    )
    launcher.bridge.engine = launcher.engine

    launcher.engine.is_running = True
    assert launcher.engine.current_tick == 0
    launcher.engine.step_tick()
    assert launcher.engine.current_tick == 1

    launcher.engine.is_running = False
    for _ in range(5):
        if not launcher.engine.is_running:
            await asyncio.sleep(0.01)
            continue
        launcher.engine.step_tick()

    assert launcher.engine.current_tick == 1
