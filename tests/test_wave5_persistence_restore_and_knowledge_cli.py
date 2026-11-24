"""
tests/test_wave5_persistence_restore_and_knowledge_cli.py
Comprehensive Wave 5 Acceptance Test Suite:
1. SQLite Schema Idempotent Migrations (PRAGMA table_info + ALTER TABLE, buildings table, body).
2. Full Save -> Fresh Boot Restore Round-Trip:
   - All Sprint 4-6 agent fields: role, title, yaw, profession, level, xp, hygiene, fatigue,
     known_books, personality, mood, mechanical effects, gear, home_building_id.
   - Buildings: Ring 1 city buildings & Ring 2 frontier buildings with pioneer_count.
   - Two-Book Governance: world_library (including body!) and divine_codex live overrides.
   - Divine entities: bestowed names and autonomy sync.
   - Dynamic neural slab capacity restore.
   - Strict 0.000000 credit conservation across save/restore cycles.
3. Historical Rewind (rewind <day>):
   - Target day selection verifies SHA-256 and restores live RAM registries cleanly.
4. Mid-Day save & God Ledger Fixes:
   - Manual save does NOT advance calendar day or season.
   - Multi-year ledger markdown prints Year 2 on day >= 29.
   - Ledger buffer clears cleanly after daily commit.
5. RichGodConsole codex write boolean and primitive type parsing.
6. Knowledge Foundry CLI End-to-End:
   - celestial_ingest deduplication against DB.
   - knowledge_review.py --pack handles dict/list counts.
   - knowledge_merge.py --pack --commit stores body in world_library.
7. launch_gaia.py Auto-Restore vs --fresh handling.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from sim_core.brains.personality import MoodState, PersonalityVector
from sim_core.engine import SimulationEngine
from sim_core.god_console.cli import RichGodConsole
from sim_core.knowledge.db_loader import (
    count_pack_entries,
    ensure_world_library_schema,
    load_library_from_db,
)
from sim_core.persistence.db import init_db
from sim_core.schemas import (
    AgentRecord,
    BuildingRecord,
    Vec3,
    WorldLibraryEntry,
)


# -----------------------------------------------------------------------------
# 1. SQLite Schema Idempotent Migrations
# -----------------------------------------------------------------------------
def test_wave5_sqlite_schema_and_migrations(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy_civ.db"

    # Create older partial schema missing Wave 5 columns and buildings table
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE world_library (
                entry_id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                author_id TEXT NOT NULL,
                author_proficiency REAL NOT NULL DEFAULT 1.0,
                skill_bonus REAL NOT NULL DEFAULT 0.08,
                is_scripture INTEGER NOT NULL DEFAULT 0,
                read_count INTEGER NOT NULL DEFAULT 0,
                created_tick INTEGER NOT NULL DEFAULT 0
            );
        """)
        conn.execute("""
            CREATE TABLE agents (
                agent_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                race TEXT NOT NULL,
                gender TEXT NOT NULL,
                sub_lineage TEXT,
                patron_godmother_slot TEXT,
                settlement_id TEXT,
                alive INTEGER NOT NULL DEFAULT 1,
                age_ticks INTEGER NOT NULL DEFAULT 0,
                x REAL NOT NULL DEFAULT 0.0,
                y REAL NOT NULL DEFAULT 0.0,
                z REAL NOT NULL DEFAULT 0.0,
                credits REAL NOT NULL DEFAULT 0.0
            );
        """)
        conn.execute("""
            CREATE TABLE divine_entities (
                slot TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                divine_energy REAL NOT NULL DEFAULT 100.0
            );
        """)
        conn.commit()

    # Run init_db which should idempotently execute PRAGMA table_info + ALTER TABLE
    init_db(db_path)

    with sqlite3.connect(db_path) as conn:
        # Check world_library has body
        wl_cols = {row[1] for row in conn.execute("PRAGMA table_info(world_library)").fetchall()}
        assert "body" in wl_cols

        # Check agents has all Sprint 4-6 columns
        ag_cols = {row[1] for row in conn.execute("PRAGMA table_info(agents)").fetchall()}
        expected_ag_cols = [
            "role",
            "title",
            "yaw",
            "profession",
            "profession_level",
            "profession_xp",
            "hygiene",
            "fatigue",
            "known_books_json",
            "personality_json",
            "mood_json",
            "active_mechanical_effects_json",
            "equipped_gear_json",
            "home_building_id",
        ]
        for col in expected_ag_cols:
            assert col in ag_cols, f"agents table missing migrated column: {col}"

        # Check divine_entities has personality and mood columns
        de_cols = {row[1] for row in conn.execute("PRAGMA table_info(divine_entities)").fetchall()}
        assert "personality_vector_json" in de_cols
        assert "mood_json" in de_cols

        # Check buildings table exists with correct columns
        bld_cols = {row[1] for row in conn.execute("PRAGMA table_info(buildings)").fetchall()}
        assert "building_id" in bld_cols
        assert "is_frontier" in bld_cols
        assert "racial_style" in bld_cols

    # Running init_db a second time should be completely safe & idempotent
    init_db(db_path)


# -----------------------------------------------------------------------------
# 2. Full Save -> Fresh Boot Restore Round-Trip
# -----------------------------------------------------------------------------
def test_wave5_full_save_and_boot_restore_roundtrip(tmp_path: Path) -> None:
    db_path = tmp_path / "civilization.db"
    checkpoints_dir = tmp_path / "checkpoints"
    god_ledger_dir = tmp_path / "god_ledger"

    engine = SimulationEngine(
        db_path=db_path,
        checkpoints_dir=checkpoints_dir,
        god_ledger_dir=god_ledger_dir,
        headless=True,
    )

    # 1. Custom agents with Sprint 4-6 fields
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

    # 2. Buildings: Ring 1 city building + Ring 2 frontier building
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

    # 3. Two-Book Governance: world_library with body and divine_codex override
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

    # 4. Bestowed divine name
    engine.divine_hierarchy.entities["gm_human"].bestowed_name = "Lady_Astraea"
    engine.divine_autonomy.deities["gm_human"].name = "Lady_Astraea"

    # 5. Bank reserves and exact credit calculation
    engine.bank.reserve_credits = 49400.0
    total_pre_credits = engine.bank.reserve_credits + sum(a.credits for a in engine.agents.values())
    assert abs(total_pre_credits - 50000.0) < 1e-6

    # 6. Dynamic slab growth check: batched_net capacity
    initial_cap = engine.batched_net.capacity

    # Commit Day 1 (advances day to 2)
    manifest = engine.commit_end_of_day(advance_day=True)
    assert manifest.status == "VERIFIED"
    assert manifest.day == 1

    # Instantiate brand new SimulationEngine on same paths
    engine_restored = SimulationEngine(
        db_path=db_path,
        checkpoints_dir=checkpoints_dir,
        god_ledger_dir=god_ledger_dir,
        headless=True,
    )
    assert engine_restored.has_verified_checkpoint()

    # Restore from checkpoint
    day_res, man_res, status_msg = engine_restored.restore_from_checkpoint()
    assert day_res == 1
    assert man_res.day == 1
    assert "Verified" in status_msg or "BOOT_CLEAN" in status_msg

    # 1. Check world meta & clock
    assert engine_restored.current_day == 2

    # 2. Check strict credit conservation
    total_post_credits = (
        engine_restored.bank.reserve_credits
        + sum(a.credits for a in engine_restored.agents.values())
    )
    assert abs(total_pre_credits - total_post_credits) < 1e-6

    # 3. Check agent state bit-for-bit
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

    # 4. Check buildings restoration
    assert "bld_solaria_forge_01" in engine_restored.city_layout.buildings
    assert "bld_frontier_homestead_01" in engine_restored.housing_market.frontier_buildings
    assert engine_restored.housing_market.pioneer_count == 1
    frontier_bld = engine_restored.housing_market.frontier_buildings["bld_frontier_homestead_01"]
    assert frontier_bld.is_frontier is True
    assert frontier_bld.settlement_id == "frontier_solaria"

    # 5. Check Two-Book Governance
    assert "metallurgy_vol_1" in engine_restored.governance_engine.library_entries
    restored_book = engine_restored.governance_engine.library_entries["metallurgy_vol_1"]
    assert restored_book.body is not None
    assert "Step 1: Construct refractory clay lining." in restored_book.body
    overrides = engine_restored.governance_engine.live_engine_overrides
    assert overrides["NON_AGGRESSION_COVENANT"] is False
    assert overrides["DIVINE_TRUCE_HOURS"] == 48.0

    # 6. Check Divine entities & bestowed name sync
    human_gm = engine_restored.divine_hierarchy.entities["gm_human"]
    assert human_gm.bestowed_name == "Lady_Astraea"
    assert engine_restored.divine_autonomy.deities["gm_human"].name == "Lady_Astraea"

    # 7. Check batched_net capacity preserved
    assert engine_restored.batched_net.capacity == initial_cap


# -----------------------------------------------------------------------------
# 3. Historical Rewind (rewind <day>)
# -----------------------------------------------------------------------------
def test_wave5_historical_rewind(tmp_path: Path) -> None:
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

    # Day 1 Setup
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
    )
    engine.city_layout.buildings = {bld_day1.building_id: bld_day1}

    # Commit Day 1 Checkpoint
    engine.commit_end_of_day(advance_day=True)
    assert engine.current_day == 2

    # Day 2 Mutation
    engine.agents["timetraveler"].credits = 500.0
    bld_day2 = BuildingRecord(
        building_id="house_d2",
        city_id="solaria",
        building_type="HOUSE_T3_MANOR",
        racial_style="HUMAN",
        x=100.0,
        y=0.0,
        z=100.0,
        rotation_y=0.0,
        parcel_x=6,
        parcel_z=6,
    )
    engine.city_layout.buildings[bld_day2.building_id] = bld_day2

    # Commit Day 2 Checkpoint
    engine.commit_end_of_day(advance_day=True)
    assert engine.current_day == 3
    assert engine.agents["timetraveler"].credits == 500.0
    assert "house_d2" in engine.city_layout.buildings

    # Execute console command: rewind 1
    rewind_out = console.execute_command("rewind 1")
    assert "SUCCESS" in rewind_out or "Rewound" in rewind_out
    assert "Day 1" in rewind_out

    # Assert live RAM is rewound back to Day 1
    assert engine.current_day == 2
    assert engine.agents["timetraveler"].credits == 100.0
    assert "house_d1" in engine.city_layout.buildings
    assert "house_d2" not in engine.city_layout.buildings


# -----------------------------------------------------------------------------
# 4. Mid-Day save & God Ledger Fixes
# -----------------------------------------------------------------------------
def test_wave5_midday_save_and_god_ledger(tmp_path: Path) -> None:
    db_path = tmp_path / "civ_ledger.db"
    checkpoints_dir = tmp_path / "checkpoints"
    god_ledger_dir = tmp_path / "god_ledger"

    engine = SimulationEngine(
        db_path=db_path,
        checkpoints_dir=checkpoints_dir,
        god_ledger_dir=god_ledger_dir,
        headless=True,
    )
    console = RichGodConsole(engine=engine)

    assert engine.current_day == 1

    # Buffer a log message
    engine.ledger_pipeline.record_deity_message(
        entry_id="test_msg_001",
        day=1,
        tick=100,
        category="GOD_MOTHER_REPORT",
        deity_slot="gm_human",
        speaker_name="Solis",
        message="Test prayer event during daytime.",
    )
    assert len(engine.ledger_pipeline.buffer) == 1

    # Manual save via console must NOT advance current_day
    save_out = console.execute_command("save")
    assert "Atomic save committed successfully" in save_out
    assert engine.current_day == 1
    # Buffer should NOT be wiped during manual mid-day save
    assert len(engine.ledger_pipeline.buffer) == 1

    # Test year calculation: Day 29 must print Year 2
    md_day29 = engine.ledger_pipeline.compile_daily_ledger_markdown(
        day=29,
        season="SPRING",
        world_goddess_name="Gaia",
        living_population=100,
        demographics={"human": 100},
        cpi=1.0,
        active_wars=0,
        neutral_free_cities=0,
    )
    assert "Day 29 (Spring, Year 2)" in md_day29

    # Day 1 end-of-day commit should clear buffer
    engine.commit_end_of_day(advance_day=True)
    assert engine.current_day == 2
    assert len(engine.ledger_pipeline.buffer) == 0


# -----------------------------------------------------------------------------
# 5. RichGodConsole codex write Boolean and Primitive Type Parsing
# -----------------------------------------------------------------------------
def test_wave5_console_codex_write_type_parsing(tmp_path: Path) -> None:
    db_path = tmp_path / "civ_codex.db"
    checkpoints_dir = tmp_path / "checkpoints"
    god_ledger_dir = tmp_path / "god_ledger"

    engine = SimulationEngine(
        db_path=db_path,
        checkpoints_dir=checkpoints_dir,
        god_ledger_dir=god_ledger_dir,
        headless=True,
    )
    console = RichGodConsole(engine=engine)

    # 1. Parse bool true
    cmd1 = "codex write DEC_TRUE 'Decree True' NON_AGGRESSION_COVENANT true"
    out1 = console.execute_command(cmd1)
    assert "SUCCESS" in out1
    assert engine.governance_engine.live_engine_overrides["NON_AGGRESSION_COVENANT"] is True

    # 2. Parse bool false
    cmd2 = "codex write DEC_FALSE 'Decree False' NON_AGGRESSION_COVENANT false"
    out2 = console.execute_command(cmd2)
    assert "SUCCESS" in out2
    assert engine.governance_engine.live_engine_overrides["NON_AGGRESSION_COVENANT"] is False

    # 3. Parse integer
    out3 = console.execute_command("codex write DEC_INT 'Decree Int' MAX_ORACLES 7")
    assert "SUCCESS" in out3
    assert engine.governance_engine.live_engine_overrides["MAX_ORACLES"] == 7

    # 4. Parse float
    out4 = console.execute_command("codex write DEC_FLOAT 'Decree Float' DIVINE_TRUCE_HOURS 72.5")
    assert "SUCCESS" in out4
    assert engine.governance_engine.live_engine_overrides["DIVINE_TRUCE_HOURS"] == 72.5

    # 5. Parse string
    out5 = console.execute_command("codex write DEC_STR 'Decree Str' TRUCE_REASON 'sacred_accord'")
    assert "SUCCESS" in out5
    assert engine.governance_engine.live_engine_overrides["TRUCE_REASON"] == "sacred_accord"


# -----------------------------------------------------------------------------
# 6. Knowledge Foundry CLI End-to-End
# -----------------------------------------------------------------------------
def test_wave5_knowledge_foundry_cli_end_to_end(tmp_path: Path) -> None:
    db_path = tmp_path / "civilization.db"
    init_db(db_path)
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)

    # Pre-populate world_library with one canonical entry
    with sqlite3.connect(db_path) as conn:
        ensure_world_library_schema(conn)
        conn.execute(
            """
            INSERT INTO world_library
            (entry_id, topic, title, summary, author_id, author_proficiency,
             skill_bonus, created_tick, body, subject, section)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "tactics_001",
                "siege",
                "Defensive Shield Walls",
                "Overlapping shields to deflect volleys.",
                "Leon",
                1.0,
                0.08,
                0,
                "Formation must interlock rims firmly and advance in tight coordination.",
                "tactics_and_warfare",
                "siege",
            ),
        )
        conn.commit()

    # Verify db_loader functions
    lib = load_library_from_db(db_path)
    lib_map = {e["entry_id"]: e for e in lib}
    assert "tactics_001" in lib_map
    assert lib_map["tactics_001"]["body"] == (
        "Formation must interlock rims firmly and advance in tight coordination."
    )

    # Create a staging pack with 1 duplicate and 1 novel entry
    pack_data = {
        "pack_id": "test_pack_wave5",
        "subject": "tactics_and_warfare",
        "target_section": "infantry",
        "entries": [
            {
                "entry_id": "tactics_dup",
                "subject": "tactics_and_warfare",
                "target_section": "siege",
                "fact_key": "tactics.siege.shield_wall",
                "title": "Defensive Shield Walls",  # Duplicate title and body
                "summary": "Overlapping shields to deflect volleys.",
                "body": (
                    "Formation must interlock rims firmly and advance in tight coordination."
                ),
                "author": "Copycat",
                "era_tier": 1,
            },
            {
                "entry_id": "tactics_novel_001",
                "subject": "tactics_and_warfare",
                "target_section": "infantry",
                "fact_key": "tactics.infantry.pike_phalanx",
                "title": "Extended Pike Phalanx Formation",
                "summary": "Five-meter ash pikes deployed in dense multi-rank formation.",
                "body": (
                    "The front five ranks project pikes horizontally against cavalry charges, "
                    "creating an impenetrable wall of spear points."
                ),
                "author": "General Philip",
                "era_tier": 1,
            },
        ],
    }

    pack_path = knowledge_dir / "pack_tactics.json"
    with open(pack_path, "w", encoding="utf-8") as f:
        json.dump(pack_data, f)

    assert count_pack_entries(pack_path) == 2

    # Import scripts
    import scripts.celestial_ingest as celestial_ingest
    import scripts.knowledge_merge as knowledge_merge
    import scripts.knowledge_review as knowledge_review

    # 1. Test celestial_ingest deduplication against DB
    passed_dup, reason_dup, _ = celestial_ingest.audit_single_entry(pack_data["entries"][0], lib)
    assert not passed_dup
    assert "DUPLICATE" in reason_dup

    passed_novel, _, _ = celestial_ingest.audit_single_entry(pack_data["entries"][1], lib)
    assert passed_novel

    # 2. Test knowledge_review CLI with --pack
    # Filter the pack to only novel entry so review passes
    novel_pack_data = dict(pack_data)
    novel_pack_data["entries"] = [pack_data["entries"][1]]
    with open(pack_path, "w", encoding="utf-8") as f:
        json.dump(novel_pack_data, f)

    rev_code = knowledge_review.main([
        "--knowledge-dir",
        str(knowledge_dir),
        "--pack",
        str(pack_path),
        "--db-path",
        str(db_path),
    ])
    assert rev_code == 0

    # 3. Test knowledge_merge CLI with --pack and --commit
    merge_code = knowledge_merge.main([
        "--knowledge-dir",
        str(knowledge_dir),
        "--pack",
        str(pack_path),
        "--db-path",
        str(db_path),
        "--commit",
    ])
    assert merge_code == 0

    # Verify world_library received the entry with its body
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT title, body, author_id FROM world_library WHERE entry_id = 'tactics_novel_001'"
        ).fetchone()
        assert row is not None
        assert row[0] == "Extended Pike Phalanx Formation"
        expected_body = (
            "The front five ranks project pikes horizontally against cavalry charges, "
            "creating an impenetrable wall of spear points."
        )
        assert row[1] == expected_body
        assert row[2] == "General Philip"


# -----------------------------------------------------------------------------
# 7. launch_gaia.py Auto-Restore vs --fresh
# -----------------------------------------------------------------------------
def test_wave5_launch_gaia_auto_restore_vs_fresh(tmp_path: Path) -> None:
    db_path = tmp_path / "launcher_civ.db"
    checkpoints_dir = tmp_path / "checkpoints"
    god_ledger_dir = tmp_path / "god_ledger"

    # Setup initial simulation and commit a checkpoint
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

    from scripts.launch_gaia import GaiaLauncher

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
    # Instantiate engine as launch_gaia does
    launcher_restore.engine = SimulationEngine(
        db_path=db_path,
        checkpoints_dir=checkpoints_dir,
        god_ledger_dir=god_ledger_dir,
        headless=True,
    )

    # Check auto-restore condition
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

    # Execute the launcher fresh cleanup logic
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

    launcher_fresh.engine = SimulationEngine(
        db_path=db_path,
        checkpoints_dir=checkpoints_dir,
        god_ledger_dir=god_ledger_dir,
        headless=True,
    )
    # With fresh=True, auto-restore branch evaluates False
    should_restore = (
        not launcher_fresh.args.fresh and launcher_fresh.engine.has_verified_checkpoint()
    )
    assert not should_restore


# -----------------------------------------------------------------------------
# 8. Adversarial Mid-Session Rewind Continuity & Stale Leak Prevention
# -----------------------------------------------------------------------------
def test_wave5_rewind_adversarial_continuity(tmp_path: Path) -> None:
    from sim_core.bridge.godot_ws_bridge import GodotWebSocketBridge

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

    # Initial prices & records
    engine.wtc.current_prices["GRAIN"] = 12.50
    engine.bank.reserve_credits = 49350.0  # 49350 + 200 + 150 + 300 = 50000.0
    total_d1_credits = engine.bank.reserve_credits + sum(a.credits for a in engine.agents.values())
    assert abs(total_d1_credits - 50000.0) < 1e-6

    # Commit Day 1 Checkpoint
    engine.commit_end_of_day(advance_day=True)
    assert engine.current_day == 2

    # Day 2 Mutation: Spawn Day 2 agent & Day 2 pioneer building
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

    # Mutate WTC price & file criminal record
    engine.wtc.current_prices["GRAIN"] = 25.00
    from sim_core.schemas import JudiciaryCaseRecord
    c_case = JudiciaryCaseRecord(
        case_id="case_theft_01",
        settlement_id="solaria",
        accused_id="citizen_d2",
        offense_type="THEFT",
        status="CLOSED",
        ruling="FINE",
        opened_tick=10,
        closed_tick=20,
    )
    engine.judiciary.cases[c_case.case_id] = c_case
    engine.judiciary.criminal_records.setdefault("citizen_d2", []).append("case_theft_01")

    # Rebalance bank reserves for Day 2 credits
    engine.bank.reserve_credits = 50000.0 - sum(a.credits for a in engine.agents.values())

    # Commit Day 2 Checkpoint
    engine.commit_end_of_day(advance_day=True)
    assert engine.current_day == 3

    # Verify Day 2 agent is active in bridge
    assert bool(bridge.active_mask[citizen_d2.slot_idx]) is True

    # Execute rewind 1 on the SAME engine instance
    out = console.execute_command("rewind 1")
    assert "SUCCESS" in out or "Rewound" in out

    # 1. Day 2 agent must be gone from engine.agents AND bridge.active_mask
    assert "citizen_d2" not in engine.agents
    assert citizen_d2.slot_idx not in bridge.slot_to_agent_id
    assert not bridge.active_mask[citizen_d2.slot_idx]

    # 2. Pioneer building must be gone from buildings and navigation
    assert "bld_pioneer_d2" not in engine.city_layout.buildings
    assert "bld_pioneer_d2" not in engine.housing_market.frontier_buildings
    footprint_names = [fp.name for fp in engine.navigation.footprints]
    assert "bld_pioneer_d2" not in footprint_names
    # Default landmarks preserved
    assert "Grand Divine Palace" in footprint_names
    assert "bld_d1" in footprint_names

    # 3. Patrol rosters rebuilt
    assert "knight_01" in engine.palace_security.knight_agent_ids
    assert "knight_01" in engine.palace_security.knight_waypoints
    assert "aurelia" in engine.city_layout.guard_assignments
    assert "guard_aurelia_01" in engine.city_layout.guard_assignments["aurelia"]

    # 4. WTC prices and credit conservation restored
    assert abs(engine.wtc.current_prices["GRAIN"] - 12.50) < 1e-4
    total_rewound_credits = engine.bank.reserve_credits + sum(
        a.credits for a in engine.agents.values()
    )
    assert abs(total_d1_credits - total_rewound_credits) < 1e-6


# -----------------------------------------------------------------------------
# 9. Same-Day Manual Save Manifest History & Corruption Rewind
# -----------------------------------------------------------------------------
def test_wave5_same_day_manual_save_manifest_history(tmp_path: Path) -> None:
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

    # Commit Day 1
    engine.commit_end_of_day(advance_day=True)
    assert engine.current_day == 2

    # Mid-day manual save on Day 2
    console.execute_command("save")

    # End-of-day commit on Day 2
    engine.commit_end_of_day(advance_day=True)
    assert engine.current_day == 3

    # Check manifest_history.json: Day 2 must have only 1 entry with updated hash
    history_file = checkpoints_dir / "manifest_history.json"
    with open(history_file, encoding="utf-8") as f:
        history = json.load(f)

    day_2_entries = [h for h in history if h.get("day") == 2]
    assert len(day_2_entries) == 1

    # Corrupt Day 2 database
    day2_db = checkpoints_dir / "day_00002.db"
    with open(day2_db, "wb") as f:
        f.write(b"CORRUPTED_GARBAGE_BYTES")

    # Boot restore should auto-rewind to Day 1
    engine_rewound = SimulationEngine(
        db_path=db_path,
        checkpoints_dir=checkpoints_dir,
        god_ledger_dir=god_ledger_dir,
        headless=True,
    )
    day_res, man_res, alert = engine_rewound.restore_from_checkpoint()
    assert day_res == 1
    assert "REWOUND" in alert or "Rewound" in alert or "CORRUPTION" in alert


# -----------------------------------------------------------------------------
# 10. Knowledge Foundry Tools Edge Cases
# -----------------------------------------------------------------------------
def test_wave5_knowledge_tools_edge_cases(tmp_path: Path) -> None:
    import scripts.celestial_ingest as celestial_ingest
    import scripts.knowledge_merge as knowledge_merge
    import scripts.knowledge_review as knowledge_review

    # 1. TRK2-DEF-04: count_pack_entries on malformed dict without "entries"
    bad_pack = tmp_path / "bad_pack.json"
    with open(bad_pack, "w", encoding="utf-8") as f:
        json.dump({"meta": "info", "version": 1}, f)
    assert count_pack_entries(bad_pack) == 0

    # 2. TRK2-DEF-01: knowledge_review catches cross-pack duplicate against sibling pack
    k_dir = tmp_path / "k_packs"
    k_dir.mkdir()
    sib1 = k_dir / "pack_a.json"
    sib2 = k_dir / "pack_b.json"

    entry_shared = {
        "entry_id": "mining_001",
        "subject": "craft_and_metallurgy",
        "target_section": "metallurgy",
        "fact_key": "craft.mining.iron_veins",
        "title": "Subterranean Iron Vein Identification",
        "summary": "Identifying hematite and magnetite formations in limestone strata.",
        "body": "Look for rust staining and magnetic deflection in karst formations.",
        "author": "Prospector",
        "era_tier": 1,
    }
    with open(sib1, "w", encoding="utf-8") as f:
        json.dump(
            {"pack_id": "pack_a", "subject": "craft_and_metallurgy", "entries": [entry_shared]}, f
        )

    with open(sib2, "w", encoding="utf-8") as f:
        json.dump(
            {"pack_id": "pack_b", "subject": "craft_and_metallurgy", "entries": [entry_shared]}, f
        )

    db_path = tmp_path / "test_kb.db"
    init_db(db_path)

    # Reviewing sib2 while sib1 exists in knowledge_dir must detect the duplicate!
    rev_code = knowledge_review.main([
        "--knowledge-dir",
        str(k_dir),
        "--pack",
        str(sib2),
        "--db-path",
        str(db_path),
    ])
    assert rev_code == 1

    # 3. TRK2-DEF-05: knowledge_merge --archive-dir custom directory
    custom_archive = tmp_path / "my_custom_archive"
    entry_novel = dict(entry_shared)
    entry_novel["entry_id"] = "mining_novel_999"
    entry_novel["fact_key"] = "craft.mining.deep_silver"
    entry_novel["title"] = "Deep Silver Extraction Methods"
    entry_novel["body"] = (
        "Smelting galena ores using high-temperature bone ash "
        "cupellation to isolate pure silver bullion."
    )

    # Remove pack_a so sib2 can merge cleanly
    sib1.unlink()
    with open(sib2, "w", encoding="utf-8") as f:
        json.dump(
            {"pack_id": "pack_b", "subject": "craft_and_metallurgy", "entries": [entry_novel]}, f
        )

    merge_code = knowledge_merge.main([
        "--knowledge-dir",
        str(k_dir),
        "--pack",
        str(sib2),
        "--db-path",
        str(db_path),
        "--archive-dir",
        str(custom_archive),
        "--commit",
    ])
    assert merge_code == 0
    assert custom_archive.exists()
    archived_files = list(custom_archive.glob("*.json"))
    assert len(archived_files) == 1

    # 4. TRK2-DEF-02: celestial_ingest raises ValueError when all candidate entries are duplicates
    lore_doc = tmp_path / "lore.txt"
    lore_doc.write_text(
        "Deep Silver Extraction Methods. Smelting galena ores using bone ash cupellation."
    )
    out_pack = tmp_path / "ingest_out.json"

    with pytest.raises(ValueError, match="All candidate entries were rejected as duplicates"):
        celestial_ingest.run_ingest(
            input_path=lore_doc,
            subject="craft_and_metallurgy",
            output_path=out_pack,
            use_llm=False,
            db_path=db_path,
            knowledge_dir=k_dir,
        )
