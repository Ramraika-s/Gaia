"""
tests/test_qa_loop.py
Acceptance tests for Phase 0:
- .qa_loop/ file lock acquisition and LOCK_VIOLATION enforcement
- SHA-256 immutable snapshot creation and verification
- 4-Stage atomic rollback & purge protocol (with bit-for-bit SHA-256 verification)
- Tampered/corrupted backup detection aborting cleanly (Stage 1 pre-flight)
- precautions.json schema validation
"""

import json
from pathlib import Path

import pytest

from scripts.qa_loop_guard import (
    HANDOFF_REPORTS_DIR,
    PRECAUTIONS_PATH,
    LockViolationError,
    RollbackAbortedError,
    acquire_locks,
    check_lock_permission,
    compute_sha256,
    create_backup_snapshot,
    load_file_locks,
    purge_backup_on_success,
    release_locks,
    rollback_atomic,
)


def test_precautions_json_schema():
    """Verifies .qa_loop/precautions.json conforms to AGENTS.md Section 7.2.A."""
    assert PRECAUTIONS_PATH.exists(), "precautions.json must exist"
    with open(PRECAUTIONS_PATH, encoding="utf-8") as f:
        data = json.load(f)

    assert "global_rules" in data and isinstance(data["global_rules"], list)
    assert len(data["global_rules"]) >= 3
    assert "anti_patterns_detected" in data and isinstance(data["anti_patterns_detected"], list)
    assert "environment_constraints" in data
    constraints = data["environment_constraints"]
    assert constraints.get("python_manager") == "uv"
    assert constraints.get("pinned_python") == "3.12"


def test_lock_acquisition_and_violation(tmp_path: Path):
    """Verifies exclusive locks raise LOCK_VIOLATION on concurrent access by another agent."""
    test_file = tmp_path / "protected_module.py"
    test_file.write_text("# initial content", encoding="utf-8")

    task_id = "test_task_lock_01"
    agent_a = "subagent_alpha"
    agent_b = "subagent_beta"

    try:
        # Agent A acquires exclusive lock
        acquire_locks(task_id, agent_a, [test_file], mode="EXCLUSIVE_RW", timeout_minutes=5)

        # Agent A should pass permission check
        check_lock_permission(agent_a, test_file, write=True)

        # Agent B accessing or attempting to acquire lock must trigger LockViolationError
        with pytest.raises(LockViolationError) as exc_info:
            check_lock_permission(agent_b, test_file, write=True)
        assert "LOCK_VIOLATION" in str(exc_info.value)
        assert agent_a in str(exc_info.value)

        with pytest.raises(LockViolationError) as exc_info2:
            acquire_locks("another_task", agent_b, [test_file])
        assert "LOCK_VIOLATION" in str(exc_info2.value)

    finally:
        # Cleanup locks
        release_locks(agent_id=agent_a, task_id=task_id)

    # After release, Agent B can acquire cleanly
    acquire_locks("task_beta", agent_b, [test_file], mode="EXCLUSIVE_RW", timeout_minutes=5)
    check_lock_permission(agent_b, test_file, write=True)
    release_locks(agent_id=agent_b, task_id="task_beta")


def test_sha256_backup_and_atomic_rollback(tmp_path: Path):
    """
    Verifies full lifecycle:
    1. SHA-256 backup creation
    2. Live file mutation
    3. 4-Stage atomic rollback restoring bit-for-bit identical state
    4. Purge of backup directory & creation of handoff report
    """
    target_file = tmp_path / "world_state.py"
    original_code = "ORIGINAL_STATE_CANONICAL_HASH_12345\nvalue = 42\n"
    target_file.write_text(original_code, encoding="utf-8")
    original_sha = compute_sha256(target_file)

    task_id = f"test_rollback_{tmp_path.name}"
    subagent_id = "test_subagent_01"

    # Step 1: Create backup snapshot
    task_backup_dir = create_backup_snapshot(task_id, subagent_id, [target_file])
    assert task_backup_dir.exists()
    manifest_file = task_backup_dir / "manifest.json"
    assert manifest_file.exists()

    with open(manifest_file, encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["task_id"] == task_id

    # Step 2: Mutate live file (simulating broken edit / failed attempt 3)
    target_file.write_text("BROKEN_CODE_SYNTAX_ERROR\nvalue = -999\n", encoding="utf-8")
    assert compute_sha256(target_file) != original_sha

    # Step 3: Execute 4-Stage Atomic Rollback
    history = [{"attempt": 1, "hypothesis": "Failed edit", "result": "FAILED"}]
    report = rollback_atomic(
        task_id=task_id,
        subagent_id=subagent_id,
        attempts_used=3,
        attempt_history=history,
        root_cause_analysis="Simulated test failure requiring atomic restore.",
    )

    # Step 4: Verify restored file bit-for-bit
    restored_code = target_file.read_text(encoding="utf-8")
    assert restored_code == original_code
    assert compute_sha256(target_file) == original_sha

    # Step 5: Verify backup dir was purged
    assert not task_backup_dir.exists()

    # Step 6: Verify handoff report committed
    assert report["rollback_transaction"]["status"] == "COMMITTED"
    assert report["rollback_transaction"]["checksums_verified"] is True
    assert report["rollback_transaction"]["backup_purged"] is True

    report_path = HANDOFF_REPORTS_DIR / f"{task_id}_{subagent_id}.json"
    assert report_path.exists()
    # Clean up test report
    report_path.unlink()


def test_rollback_aborted_on_tampered_backup(tmp_path: Path):
    """
    Verifies Stage 1 Pre-Flight validation:
    If a backup .orig file is corrupted, rollback ABORTS immediately
    without modifying live files.
    """
    target_file = tmp_path / "tamper_target.py"
    target_file.write_text("PRISTINE_ORIGINAL_LINE\n", encoding="utf-8")
    task_id = f"test_tamper_{tmp_path.name}"
    subagent_id = "test_subagent_tamper"

    task_backup_dir = create_backup_snapshot(task_id, subagent_id, [target_file])

    # Mutate live file
    target_file.write_text("LIVE_MUTATED_CONTENT\n", encoding="utf-8")

    # Corrupt the backup file
    with open(task_backup_dir / "manifest.json", encoding="utf-8") as f:
        manifest = json.load(f)
    rel_key = list(manifest["files"].keys())[0]
    orig_rel = manifest["files"][rel_key]["backup_rel_path"]
    orig_path = task_backup_dir / orig_rel
    orig_path.write_text("TAMPERED_BACKUP_CONTENT\n", encoding="utf-8")

    # Attempt rollback -> MUST raise RollbackAbortedError in Stage 1
    with pytest.raises(RollbackAbortedError) as exc_info:
        rollback_atomic(task_id, subagent_id)
    assert "ROLLBACK_ABORTED" in str(exc_info.value)

    # Live file must remain untouched in its current state (not overwritten by corrupt data)
    assert target_file.read_text(encoding="utf-8") == "LIVE_MUTATED_CONTENT\n"

    # Cleanup test backup
    import shutil

    shutil.rmtree(task_backup_dir)


def test_purge_on_success(tmp_path: Path):
    """Verifies purge_backup_on_success removes backup dir and releases locks."""
    target_file = tmp_path / "success_target.py"
    target_file.write_text("SUCCESS_CODE\n", encoding="utf-8")
    task_id = f"test_success_{tmp_path.name}"
    subagent_id = "test_subagent_success"

    acquire_locks(task_id, subagent_id, [target_file])
    task_backup_dir = create_backup_snapshot(task_id, subagent_id, [target_file])
    assert task_backup_dir.exists()

    purge_backup_on_success(task_id, subagent_id)
    assert not task_backup_dir.exists()

    # Lock must be released
    locks = load_file_locks().get("active_locks", {})
    assert task_id not in [lock_entry["task_id"] for lock_entry in locks.values()]
