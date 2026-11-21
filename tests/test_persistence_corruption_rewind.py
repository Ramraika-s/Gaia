"""
tests/test_persistence_corruption_rewind.py
Phase 1 Acceptance Tests:
- World Goddess Atomic Two-Phase Commit (SHA-256 checksums, manifest written last)
- Bit-flipping day_00002.pt fails SHA-256 check on boot, automatically rewinds
  both .db and .pt to day_00001, and logs [CORRUPTION_REWIND].
"""

import sqlite3
from pathlib import Path

from sim_core.persistence.checkpoints import WorldGoddessCheckpointManager, compute_file_sha256


def test_atomic_save_and_corruption_rewind(test_db_path: Path, tmp_path: Path):
    """
    Acceptance Requirement:
    Proves bit-flipping day_00002.pt causes startup loader to fail SHA-256 check,
    automatically rewind to day_00001 (both .db and .pt), and log [CORRUPTION_REWIND].
    """
    checkpoints_dir = tmp_path / "checkpoints"
    god_ledger_dir = tmp_path / "god_ledger"

    manager = WorldGoddessCheckpointManager(
        checkpoints_dir=checkpoints_dir,
        god_ledger_dir=god_ledger_dir,
    )

    # -------------------------------------------------------------------------
    # 1. Commit Day 1 Checkpoint
    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    # 2. Commit Day 2 Checkpoint
    # -------------------------------------------------------------------------
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

    # Verify live DB is currently at Day 2
    with sqlite3.connect(test_db_path) as conn:
        cursor = conn.execute("SELECT value_json FROM world_meta WHERE key = 'world_day'")
        val = cursor.fetchone()[0]
    assert val == "2"

    # -------------------------------------------------------------------------
    # 3. Simulate Corruption: Bit-Flip / Tamper day_00002.pt
    # -------------------------------------------------------------------------
    pt_day2_path = Path(man2.pt_path)
    with open(pt_day2_path, "r+b") as f:
        # Flip first byte
        byte = f.read(1)
        f.seek(0)
        f.write(bytes([byte[0] ^ 0xFF]))
        f.flush()

    # Verify that SHA-256 no longer matches manifest
    assert compute_file_sha256(pt_day2_path) != man2.pt_sha256

    # -------------------------------------------------------------------------
    # 4. Boot Loader Invoked: Automatic Corruption Rewind to Day 1
    # -------------------------------------------------------------------------
    restored_day, restored_manifest, alert_msg = manager.restore_or_rewind_on_boot(
        live_db_path=test_db_path,
    )

    # Acceptance Assertions:
    assert restored_day == 1, "Must rewind to Day 1 after Day 2 corruption"
    assert restored_manifest.day == 1
    assert "[CORRUPTION_REWIND]" in alert_msg
    assert "Day 1" in alert_msg

    # Verify live DB was restored bit-for-bit to Day 1 state
    with sqlite3.connect(test_db_path) as conn:
        cursor = conn.execute("SELECT value_json FROM world_meta WHERE key = 'world_day'")
        restored_val = cursor.fetchone()[0]
    assert restored_val == "1", "Live database must be rolled back to Day 1 state"
