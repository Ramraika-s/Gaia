# tests/persistence/test_db_migrations_and_atomic_checkpoints.py
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from sim_core.engine import SimulationEngine
from sim_core.god_console.cli import RichGodConsole
from sim_core.persistence.checkpoints import WorldGoddessCheckpointManager, compute_file_sha256
from sim_core.persistence.db import execute_daily_commit, init_db, run_analytics_query


def test_sqlite_schema_and_migrations(tmp_path: Path) -> None:
    """Verifies that init_db idempotently migrates legacy SQLite tables."""
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

    init_db(db_path)

    with sqlite3.connect(db_path) as conn:
        wl_cols = {row[1] for row in conn.execute("PRAGMA table_info(world_library)").fetchall()}
        assert "body" in wl_cols

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

        de_cols = {row[1] for row in conn.execute("PRAGMA table_info(divine_entities)").fetchall()}
        assert "personality_vector_json" in de_cols
        assert "mood_json" in de_cols

        bld_cols = {row[1] for row in conn.execute("PRAGMA table_info(buildings)").fetchall()}
        assert "building_id" in bld_cols
        assert "is_frontier" in bld_cols
        assert "racial_style" in bld_cols

    # Idempotent second run
    init_db(db_path)


def test_sqlite_atomic_commit_full_rollback_on_error(test_db_path: Path) -> None:
    """Proves that a mid-commit failure triggers full ROLLBACK (zero partial rows written)."""
    with sqlite3.connect(test_db_path) as conn:
        count_before = conn.execute("SELECT count(*) FROM settlements").fetchone()[0]
    assert count_before == 0

    statements = [
        (
            (
                "INSERT INTO settlements (settlement_id, name, tier, regime_type, founder_id, "
                "center_pos_json, border_parcel_ids_json, treasury_credits, tax_rate, laws_json, "
                "at_war_with_json, allied_with_json, founded_tick) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            ),
            (
                "set_001",
                "Solaria",
                "VILLAGE",
                "ELECTED",
                "agt_01",
                "{}",
                "[]",
                100.0,
                0.05,
                "{}",
                "[]",
                "[]",
                1,
            ),
        ),
        (
            "INSERT INTO non_existent_table_will_fail VALUES (1, 2, 3)",
            (),
        ),
    ]

    with pytest.raises(sqlite3.OperationalError):
        execute_daily_commit(test_db_path, statements)

    with sqlite3.connect(test_db_path) as conn:
        count_after = conn.execute("SELECT count(*) FROM settlements").fetchone()[0]
    assert count_after == 0, "Atomic commit must leave zero partial rows on failure"


def test_atomic_save_and_corruption_rewind(test_db_path: Path, tmp_path: Path) -> None:
    """Proves bit-flipping day_00002.pt causes startup loader to fail SHA-256 and rewind."""
    checkpoints_dir = tmp_path / "checkpoints"
    god_ledger_dir = tmp_path / "god_ledger"

    manager = WorldGoddessCheckpointManager(
        checkpoints_dir=checkpoints_dir,
        god_ledger_dir=god_ledger_dir,
    )

    day1_sql = [
        (
            "INSERT INTO world_meta (key, value_json) VALUES (?, ?)",
            ("world_day", "1"),
        )
    ]
    pt_day1 = {"weights": [1.0, 2.0, 3.0], "day": 1}
    ledger_day1 = "# Day 1 Ledger\nAll peaceful."

    man1 = manager.commit_daily_checkpoint(
        day=1,
        tick=10800,
        season="SPRING",
        world_goddess_name="Gaia",
        live_db_path=test_db_path,
        pt_state=pt_day1,
        ledger_markdown=ledger_day1,
        sql_deltas=day1_sql,
    )
    assert Path(man1.db_path).exists()
    assert Path(man1.pt_path).exists()
    assert man1.status == "VERIFIED"

    day2_sql = [
        (
            "UPDATE world_meta SET value_json = ? WHERE key = ?",
            ("2", "world_day"),
        )
    ]
    pt_day2 = {"weights": [4.0, 5.0, 6.0], "day": 2}
    ledger_day2 = "# Day 2 Ledger\nExpanding borders."

    man2 = manager.commit_daily_checkpoint(
        day=2,
        tick=21600,
        season="SPRING",
        world_goddess_name="Gaia",
        live_db_path=test_db_path,
        pt_state=pt_day2,
        ledger_markdown=ledger_day2,
        sql_deltas=day2_sql,
    )
    assert Path(man2.db_path).exists()
    assert Path(man2.pt_path).exists()

    with sqlite3.connect(test_db_path) as conn:
        cursor = conn.execute("SELECT value_json FROM world_meta WHERE key = 'world_day'")
        val = cursor.fetchone()[0]
    assert val == "2"

    # Bit-flip day 2 .pt
    pt_day2_path = Path(man2.pt_path)
    with open(pt_day2_path, "r+b") as f:
        byte = f.read(1)
        f.seek(0)
        f.write(bytes([byte[0] ^ 0xFF]))
        f.flush()

    assert compute_file_sha256(pt_day2_path) != man2.pt_sha256

    restored_day, restored_manifest, alert_msg = manager.restore_or_rewind_on_boot(
        live_db_path=test_db_path,
    )

    assert restored_day == 1
    assert restored_manifest.day == 1
    assert "[CORRUPTION_REWIND]" in alert_msg
    assert "Day 1" in alert_msg

    with sqlite3.connect(test_db_path) as conn:
        cursor = conn.execute("SELECT value_json FROM world_meta WHERE key = 'world_day'")
        restored_val = cursor.fetchone()[0]
    assert restored_val == "1"


def test_duckdb_read_only_attach_analytics(test_db_path: Path) -> None:
    """Proves DuckDB read-only attach queries civ.fatalities and civ.agents."""
    statements = [
        (
            "INSERT INTO agents (agent_id, slot_idx, display_name, dynasty_surname, gender, race, "
            "godmother_affinities_json, skin_hsv_json, stage, age_ticks, health, max_health, "
            "hunger, stamina, credits, credit_score, parent_ids_json, alive, pos_json, "
            "traits_json, skills_json, tradition_ids_json, updated_tick) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "agt_01",
                0,
                "Eldrin",
                "Leaf",
                "BOY",
                "ELF",
                "{}",
                "[0,0,0]",
                "ADULT",
                100,
                95.0,
                95.0,
                100.0,
                100.0,
                50.0,
                700.0,
                "[]",
                1,
                "{}",
                "{}",
                "{}",
                "[]",
                100,
            ),
        ),
        (
            "INSERT INTO fatalities (agent_id, display_name, race, age_ticks, stage_at_death, "
            "cause, season, death_day, death_tick) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("agt_99", "MortalOld", "HUMAN", 50000, "ELDER", "OLD_AGE", "WINTER", 5, 54000),
        ),
    ]
    execute_daily_commit(test_db_path, statements)

    rows_agents = run_analytics_query(
        test_db_path,
        "SELECT race, gender, credits FROM civ.agents WHERE alive = 1",
    )
    assert len(rows_agents) == 1
    assert rows_agents[0]["race"] == "ELF"
    assert rows_agents[0]["credits"] == 50.0

    rows_fatalities = run_analytics_query(
        test_db_path,
        "SELECT race, cause, season FROM civ.fatalities WHERE cause = 'OLD_AGE'",
    )
    assert len(rows_fatalities) == 1
    assert rows_fatalities[0]["race"] == "HUMAN"
    assert rows_fatalities[0]["season"] == "WINTER"


@pytest.mark.slow
def test_midday_save_and_god_ledger(tmp_path: Path) -> None:
    """Verifies manual mid-day save does not advance current_day, and ledger formats Year."""
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

    save_out = console.execute_command("save")
    assert "Atomic save committed successfully" in save_out
    assert engine.current_day == 1
    assert len(engine.ledger_pipeline.buffer) == 1

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

    engine.commit_end_of_day(advance_day=True)
    assert engine.current_day == 2
    assert len(engine.ledger_pipeline.buffer) == 0
