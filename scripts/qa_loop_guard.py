"""
scripts/qa_loop_guard.py
Deterministic implementation of the Multi-Agent QA Execution Loop & Atomic Rollback Protocol
specified in AGENTS.md Section 7.

Handles:
- Mutual exclusion lock acquisition, checks, and release in .qa_loop/file_locks.json
- Immutable SHA-256 backup snapshot creation (.qa_loop/backups/<task_id>/)
- 4-Stage Atomic Rollback Transaction:
  Read-Only Validation -> Co-Located Staging -> POSIX Swap -> Purge
- Handoff report generation (.qa_loop/handoff_reports/)
- Orphaned transaction sweep
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
QA_DIR = REPO_ROOT / ".qa_loop"
PRECAUTIONS_PATH = QA_DIR / "precautions.json"
FILE_LOCKS_PATH = QA_DIR / "file_locks.json"
BACKUPS_DIR = QA_DIR / "backups"
HANDOFF_REPORTS_DIR = QA_DIR / "handoff_reports"


class LockViolationError(Exception):
    """Raised when an operation violates active mutual-exclusion file locks."""
    pass


class RollbackAbortedError(Exception):
    """Raised when atomic rollback pre-flight validation fails."""
    pass


def compute_sha256(file_path: Path) -> str:
    """Computes SHA-256 hex digest of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def _normalize_rel_path(file_path: str | Path) -> str:
    """Normalizes path relative to REPO_ROOT as POSIX string if within repo, else absolute."""
    p = Path(file_path).resolve()
    try:
        return p.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def _resolve_live_path(path_str: str) -> Path:
    """Resolves a normalized path string back to its live Path."""
    p = Path(path_str)
    if p.is_absolute():
        return p
    return REPO_ROOT / p


# ==============================================================================
# 1. Mutual Exclusion Lock Management (.qa_loop/file_locks.json)
# ==============================================================================

def load_file_locks() -> dict[str, Any]:
    """Loads active locks from file_locks.json."""
    if not FILE_LOCKS_PATH.exists():
        return {"active_locks": {}}
    try:
        with open(FILE_LOCKS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"active_locks": {}}


def save_file_locks(data: dict[str, Any]) -> None:
    """Atomically saves locks to file_locks.json using same-parent staging."""
    QA_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = QA_DIR / ".file_locks.json.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, FILE_LOCKS_PATH)


def check_lock_permission(agent_id: str, file_path: str | Path, write: bool = True) -> None:
    """
    Checks if agent_id has permission to access file_path.
    Throws LockViolationError if locked by another active agent.
    """
    rel_path = _normalize_rel_path(file_path)
    locks = load_file_locks().get("active_locks", {})

    if rel_path in locks:
        lock = locks[rel_path]
        expires_at = datetime.datetime.fromisoformat(lock["expires_at"].replace("Z", "+00:00"))
        now = datetime.datetime.now(datetime.UTC)

        if now <= expires_at:
            if lock["owner_agent_id"] != agent_id:
                raise LockViolationError(
                    f"LOCK_VIOLATION: File '{rel_path}' is locked by '{lock['owner_agent_id']}' "
                    f"for task '{lock['task_id']}' until {lock['expires_at']}."
                )


def acquire_locks(
    task_id: str,
    agent_id: str,
    file_paths: list[str | Path],
    mode: str = "EXCLUSIVE_RW",
    timeout_minutes: int = 15,
) -> None:
    """
    Acquires exclusive locks for given files.
    Throws LockViolationError if any file is already locked by another agent.
    """
    locks_data = load_file_locks()
    active_locks = locks_data.setdefault("active_locks", {})
    now = datetime.datetime.now(datetime.UTC)
    expires = now + datetime.timedelta(minutes=timeout_minutes)

    # Pre-check all files first (all-or-nothing check)
    normalized = [_normalize_rel_path(p) for p in file_paths]
    for rel_path in normalized:
        if rel_path in active_locks:
            lock = active_locks[rel_path]
            expires_at = datetime.datetime.fromisoformat(lock["expires_at"].replace("Z", "+00:00"))
            if now <= expires_at and lock["owner_agent_id"] != agent_id:
                raise LockViolationError(
                    f"LOCK_VIOLATION: Cannot acquire lock on '{rel_path}', already held by "
                    f"'{lock['owner_agent_id']}' for task '{lock['task_id']}'."
                )

    # Assign locks
    for rel_path in normalized:
        active_locks[rel_path] = {
            "owner_agent_id": agent_id,
            "task_id": task_id,
            "mode": mode,
            "acquired_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "expires_at": expires.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    save_file_locks(locks_data)


def release_locks(
    agent_id: str | None = None,
    task_id: str | None = None,
    file_paths: list[str | Path] | None = None,
) -> int:
    """Releases active locks matching agent_id, task_id, or specific file_paths."""
    locks_data = load_file_locks()
    active_locks = locks_data.get("active_locks", {})
    to_remove = []

    target_rel_paths = {_normalize_rel_path(p) for p in file_paths} if file_paths else None

    for rel_path, lock in active_locks.items():
        if target_rel_paths and rel_path not in target_rel_paths:
            continue
        if agent_id and lock["owner_agent_id"] != agent_id:
            continue
        if task_id and lock["task_id"] != task_id:
            continue
        to_remove.append(rel_path)

    for p in to_remove:
        del active_locks[p]

    if to_remove:
        save_file_locks(locks_data)
    return len(to_remove)


# ==============================================================================
# 2. Immutable SHA-256 Snapshot Backup
# ==============================================================================

def create_backup_snapshot(
    task_id: str,
    subagent_id: str,
    file_paths: list[str | Path],
) -> Path:
    """
    Creates an immutable SHA-256 backup snapshot for task_id under .qa_loop/backups/<task_id>/.
    Returns the task backup directory path.
    """
    task_backup_dir = BACKUPS_DIR / task_id
    manifest_path = task_backup_dir / "manifest.json"
    if task_backup_dir.exists() and manifest_path.exists():
        # Already created before Attempt 1; attempts 2 & 3 must never touch existing snapshot
        return task_backup_dir

    task_backup_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "task_id": task_id,
        "subagent_id": subagent_id,
        "created_at": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": {},
    }

    for path_in in file_paths:
        rel_path = _normalize_rel_path(path_in)
        live_file = _resolve_live_path(rel_path)

        if not live_file.exists():
            continue

        if Path(rel_path).is_absolute():
            safe_name = rel_path.lstrip("/").replace("/", "_") + ".orig"
            backup_file_rel = f".external/{safe_name}"
        else:
            backup_file_rel = f"{rel_path}.orig"

        backup_file_dest = task_backup_dir / backup_file_rel
        backup_file_dest.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(live_file, backup_file_dest)
        sha256 = compute_sha256(live_file)

        manifest["files"][rel_path] = {
            "backup_rel_path": backup_file_rel,
            "original_sha256": sha256,
        }

    manifest_path = task_backup_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.flush()
        os.fsync(f.fileno())

    return task_backup_dir


# ==============================================================================
# 3. 4-Stage Atomic Rollback Transaction & Purge
# ==============================================================================

def rollback_atomic(
    task_id: str,
    subagent_id: str,
    attempts_used: int = 3,
    attempt_history: list[dict[str, Any]] | None = None,
    root_cause_analysis: str = "Rollback triggered due to max retries or fatal error.",
    recommended_strategy: str = "Re-analyze error logs and precautions before respawn.",
) -> dict[str, Any]:
    """
    Executes the 4-Stage Atomic Rollback Protocol:
      Stage 1: Pre-flight read-only validation of manifest and .orig checksums.
      Stage 2: Co-located staging in exact parent directories with fsync.
      Stage 3: Atomic POSIX swap (os.replace) and post-swap SHA-256 verification.
      Stage 4: Atomic backup directory rename to .trash_<task_id> and purge.
    Writes handoff report and releases locks.
    """
    task_backup_dir = BACKUPS_DIR / task_id
    manifest_path = task_backup_dir / "manifest.json"

    if not task_backup_dir.exists() or not manifest_path.exists():
        raise RollbackAbortedError(
            f"ROLLBACK_ABORTED: Backup manifest for task '{task_id}' not found at {manifest_path}."
        )

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    files_manifest: dict[str, dict[str, str]] = manifest.get("files", {})

    # -------------------------------------------------------------------------
    # Stage 1: Pre-Flight Validation (Read-Only)
    # -------------------------------------------------------------------------
    for _rel_path, meta in files_manifest.items():
        backup_rel = meta["backup_rel_path"]
        orig_file = task_backup_dir / backup_rel
        expected_sha = meta["original_sha256"]

        if not orig_file.exists():
            raise RollbackAbortedError(
                f"ROLLBACK_ABORTED: Missing backup file '{orig_file}'. Live files remain untouched."
            )

        actual_sha = compute_sha256(orig_file)
        if actual_sha != expected_sha:
            raise RollbackAbortedError(
                f"ROLLBACK_ABORTED: Corrupted backup '{orig_file}' "
                f"(expected {expected_sha}, got {actual_sha}). Live files remain untouched."
            )

    # -------------------------------------------------------------------------
    # Stage 2: Co-Located Staging + fsync
    # -------------------------------------------------------------------------
    staged_files: list[tuple[Path, Path, str]] = []  # (tmp_path, target_live_path, expected_sha)
    try:
        for rel_path, meta in files_manifest.items():
            orig_file = task_backup_dir / meta["backup_rel_path"]
            target_live = _resolve_live_path(rel_path)
            expected_sha = meta["original_sha256"]

            # Stage in exact same parent dir with hidden prefix
            tmp_path = target_live.parent / f".{target_live.name}.restore_tmp"
            target_live.parent.mkdir(parents=True, exist_ok=True)

            with open(orig_file, "rb") as src, open(tmp_path, "wb") as dst:
                while chunk := src.read(65536):
                    dst.write(chunk)
                dst.flush()
                os.fsync(dst.fileno())

            staged_files.append((tmp_path, target_live, expected_sha))

        # ---------------------------------------------------------------------
        # Stage 3: Atomic POSIX Swap + Re-Hash Verification
        # ---------------------------------------------------------------------
        for tmp_path, target_live, expected_sha in staged_files:
            os.replace(tmp_path, target_live)
            restored_sha = compute_sha256(target_live)
            if restored_sha != expected_sha:
                raise RuntimeError(
                    f"Post-swap SHA-256 verification failed on '{target_live}'. "
                    f"Expected {expected_sha}, got {restored_sha}."
                )

    except Exception as e:
        # Clean up any leftover .restore_tmp files on error
        for tmp_path, _, _ in staged_files:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
        raise e

    # -------------------------------------------------------------------------
    # Stage 4: Atomic Backup Purge (Commit Point) & Handoff Report
    # -------------------------------------------------------------------------
    trash_dir = BACKUPS_DIR / f".trash_{task_id}"
    if trash_dir.exists():
        shutil.rmtree(trash_dir)
    os.replace(task_backup_dir, trash_dir)
    shutil.rmtree(trash_dir)

    # Release file locks held for this task
    release_locks(agent_id=subagent_id, task_id=task_id)

    # Emit handoff report
    HANDOFF_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = HANDOFF_REPORTS_DIR / f"{task_id}_{subagent_id}.json"
    report_data = {
        "task_id": task_id,
        "subagent_id": subagent_id,
        "status": "FAILED_MAX_RETRIES",
        "rollback_transaction": {
            "status": "COMMITTED",
            "files_restored": list(files_manifest.keys()),
            "checksums_verified": True,
            "backup_purged": True,
        },
        "attempts_used": attempts_used,
        "attempt_history": attempt_history or [],
        "root_cause_analysis": root_cause_analysis,
        "recommended_next_strategy": recommended_strategy,
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())

    return report_data


def purge_backup_on_success(task_id: str, subagent_id: str) -> None:
    """Purges task backup and releases locks after successful task completion."""
    task_backup_dir = BACKUPS_DIR / task_id
    if task_backup_dir.exists():
        trash_dir = BACKUPS_DIR / f".trash_{task_id}"
        if trash_dir.exists():
            shutil.rmtree(trash_dir)
        os.replace(task_backup_dir, trash_dir)
        shutil.rmtree(trash_dir)

    release_locks(agent_id=subagent_id, task_id=task_id)


def sweep_orphaned_backups() -> list[str]:
    """
    Checks .qa_loop/backups/ for any leftover backup directories from crashed runs
    and deterministically rolls them back to ensure pristine workspace state.
    """
    if not BACKUPS_DIR.exists():
        return []

    restored_tasks = []
    for item in BACKUPS_DIR.iterdir():
        if item.is_dir() and not item.name.startswith("."):
            manifest_file = item / "manifest.json"
            if manifest_file.exists():
                try:
                    with open(manifest_file, encoding="utf-8") as f:
                        meta = json.load(f)
                    task_id = meta.get("task_id", item.name)
                    subagent_id = meta.get("subagent_id", "orphaned_recovery")
                    rollback_atomic(
                        task_id=task_id,
                        subagent_id=subagent_id,
                        root_cause_analysis="Orphaned crash recovery sweep on startup.",
                    )
                    restored_tasks.append(task_id)
                except Exception as ex:
                    print(f"Warning: Failed to recover orphaned backup {item}: {ex}")
    return restored_tasks
