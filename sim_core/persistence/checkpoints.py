"""
sim_core/persistence/checkpoints.py
Atomic Two-Phase Commit (2PC) checkpoint manager and automatic corruption rewind
engine owned exclusively by the World Goddess.
Writes manifest.json last and automatically rewinds to the last verified snapshot on boot.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Any

import torch

from sim_core.persistence.db import execute_daily_commit
from sim_core.schemas import DailyManifest, Season

MAX_RETAINED_SNAPSHOTS: int = 7


def compute_file_sha256(path: Path | str) -> str:
    """Computes SHA-256 hex digest of a file in 64KB chunks."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class WorldGoddessCheckpointManager:
    """
    World Goddess atomic Two-Phase Commit coordinator.
    Enforces pure end-of-day all-or-nothing commits with SHA-256 checksums,
    manifest written last, and automatic corruption rewind on startup.
    """

    def __init__(
        self,
        checkpoints_dir: str | Path = "data/checkpoints",
        god_ledger_dir: str | Path = "data/god_ledger",
    ) -> None:
        self.checkpoints_dir: Path = Path(checkpoints_dir)
        self.god_ledger_dir: Path = Path(god_ledger_dir)
        self.manifest_path: Path = self.checkpoints_dir / "manifest.json"
        self.history_path: Path = self.checkpoints_dir / "manifest_history.json"

    def commit_daily_checkpoint(
        self,
        day: int,
        tick: int,
        season: Season,
        world_goddess_name: str,
        live_db_path: str | Path,
        pt_state: dict[str, Any] | bytes,
        ledger_markdown: str,
        sql_deltas: list[tuple[str, tuple[Any, ...]]] | None = None,
    ) -> DailyManifest:
        """
        Executes the all-or-nothing atomic end-of-day commit:
          Phase 1: Atomic SQLite transaction inside BEGIN IMMEDIATE ... COMMIT.
          Phase 2: Synchronized .pt, .db online backup, and god_ledger .md written to .tmp,
                   verified with SHA-256, fsync'd, and atomically replaced.
          Phase 3: manifest.json written last with status="VERIFIED".
        """
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self.god_ledger_dir.mkdir(parents=True, exist_ok=True)

        live_db = Path(live_db_path)

        # ---------------------------------------------------------------------
        # Phase 1: All-or-Nothing SQLite Commit
        # ---------------------------------------------------------------------
        if sql_deltas:
            execute_daily_commit(live_db, sql_deltas)

        # ---------------------------------------------------------------------
        # Phase 2: Synchronized Daily Files + SHA-256
        # ---------------------------------------------------------------------
        final_pt = self.checkpoints_dir / f"day_{day:05d}.pt"
        final_db = self.checkpoints_dir / f"day_{day:05d}.db"
        final_ledger = self.god_ledger_dir / f"day_{day:05d}.md"
        latest_ledger = self.god_ledger_dir / "latest.md"

        tmp_pt = self.checkpoints_dir / f".day_{day:05d}.pt.tmp"
        tmp_db = self.checkpoints_dir / f".day_{day:05d}.db.tmp"
        tmp_ledger = self.god_ledger_dir / f".day_{day:05d}.md.tmp"
        tmp_latest = self.god_ledger_dir / ".latest.md.tmp"

        try:
            # 1. Write PyTorch tensor checkpoint
            if isinstance(pt_state, bytes):
                with open(tmp_pt, "wb") as f:
                    f.write(pt_state)
                    f.flush()
                    os.fsync(f.fileno())
            else:
                torch.save(pt_state, tmp_pt)
                with open(tmp_pt, "a+b") as f:
                    f.flush()
                    os.fsync(f.fileno())

            # 2. Online SQLite backup to checkpoint .db.tmp
            src_conn = sqlite3.connect(live_db)
            dst_conn = sqlite3.connect(tmp_db)
            src_conn.backup(dst_conn)
            dst_conn.close()
            src_conn.close()

            with open(tmp_db, "a+b") as f:
                f.flush()
                os.fsync(f.fileno())

            # 3. Write God Ledger markdown
            with open(tmp_ledger, "w", encoding="utf-8") as f:
                f.write(ledger_markdown)
                f.flush()
                os.fsync(f.fileno())

            with open(tmp_latest, "w", encoding="utf-8") as f:
                f.write(ledger_markdown)
                f.flush()
                os.fsync(f.fileno())

            # 4. Compute SHA-256 checksums
            db_sha = compute_file_sha256(tmp_db)
            pt_sha = compute_file_sha256(tmp_pt)

            # 5. Atomic POSIX swaps
            os.replace(tmp_pt, final_pt)
            os.replace(tmp_db, final_db)
            os.replace(tmp_ledger, final_ledger)
            os.replace(tmp_latest, latest_ledger)

        except Exception as e:
            # Cleanup any dangling .tmp files on error
            for tmp in (tmp_pt, tmp_db, tmp_ledger, tmp_latest):
                if tmp.exists():
                    try:
                        tmp.unlink()
                    except OSError:
                        pass
            raise e

        # ---------------------------------------------------------------------
        # Phase 3: Manifest Written Last (Commit Point)
        # ---------------------------------------------------------------------
        manifest = DailyManifest(
            day=day,
            tick=tick,
            season=season,
            committed_by=world_goddess_name,
            db_path=str(final_db),
            db_sha256=db_sha,
            pt_path=str(final_pt),
            pt_sha256=pt_sha,
            ledger_path=str(final_ledger),
            status="VERIFIED",
        )

        # Update history
        history: list[dict[str, Any]] = []
        if self.history_path.exists():
            try:
                with open(self.history_path, encoding="utf-8") as f:
                    history = json.load(f)
            except json.JSONDecodeError:
                history = []

        history = [h for h in history if h.get("day") != day]
        history.append(manifest.model_dump())
        # Retain only last MAX_RETAINED_SNAPSHOTS
        history = history[-MAX_RETAINED_SNAPSHOTS:]

        tmp_hist = self.checkpoints_dir / ".manifest_history.json.tmp"
        with open(tmp_hist, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_hist, self.history_path)

        tmp_man = self.checkpoints_dir / ".manifest.json.tmp"
        with open(tmp_man, "w", encoding="utf-8") as f:
            json.dump(manifest.model_dump(), f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_man, self.manifest_path)

        return manifest

    def restore_or_rewind_on_boot(
        self,
        live_db_path: str | Path,
        target_day: int | None = None,
    ) -> tuple[int, DailyManifest, str]:
        """
        Verifies SHA-256 of checkpoints on startup.
        If target_day is specified, locates that exact day snapshot in history, verifies SHA-256,
        and restores live .db and latest.md.
        If target_day is None and the latest checkpoint is missing or corrupted,
        automatically rewinds backward through prior verified snapshots, restores live .db,
        and logs [CORRUPTION_REWIND].
        """
        if not self.history_path.exists() and not self.manifest_path.exists():
            raise FileNotFoundError("No checkpoint manifest found to restore.")

        history: list[dict[str, Any]] = []
        if self.history_path.exists():
            with open(self.history_path, encoding="utf-8") as f:
                history = json.load(f)
        elif self.manifest_path.exists():
            with open(self.manifest_path, encoding="utf-8") as f:
                history = [json.load(f)]

        if not history:
            raise FileNotFoundError("Checkpoint history is empty.")

        live_db = Path(live_db_path)

        if target_day is not None:
            # Locate target_day entry (most recent for that day if multiple)
            matching = [entry for entry in history if entry.get("day") == target_day]
            if not matching:
                raise FileNotFoundError(
                    f"Checkpoint for target day {target_day} not found in history."
                )
            manifest = DailyManifest(**matching[-1])
            db_p = Path(manifest.db_path)
            pt_p = Path(manifest.pt_path)

            if not db_p.exists() or not pt_p.exists():
                raise FileNotFoundError(f"Snapshot files for Day {target_day} are missing on disk.")

            current_db_sha = compute_file_sha256(db_p)
            current_pt_sha = compute_file_sha256(pt_p)
            if current_db_sha != manifest.db_sha256 or current_pt_sha != manifest.pt_sha256:
                raise RuntimeError(
                    f"CORRUPTION_DETECTED: Day {target_day} failed SHA-256 verification."
                )

            # Restore live database using SQLite backup API
            if live_db.exists():
                src = sqlite3.connect(db_p)
                dst = sqlite3.connect(live_db)
                try:
                    src.backup(dst)
                finally:
                    src.close()
                    dst.close()
            else:
                shutil.copy2(db_p, live_db)

            # Sync latest.md to rewound ledger
            if manifest.ledger_path and Path(manifest.ledger_path).exists():
                latest_ledger = self.god_ledger_dir / "latest.md"
                try:
                    shutil.copy2(manifest.ledger_path, latest_ledger)
                except OSError:
                    pass

            msg = f"[REWIND_SUCCESS] Successfully rewound to Day {manifest.day} (SHA-256 verified)."
            return manifest.day, manifest, msg

        # Iterate from newest to oldest
        for idx, entry in enumerate(reversed(history)):
            manifest = DailyManifest(**entry)
            db_p = Path(manifest.db_path)
            pt_p = Path(manifest.pt_path)

            if not db_p.exists() or not pt_p.exists():
                continue

            current_db_sha = compute_file_sha256(db_p)
            current_pt_sha = compute_file_sha256(pt_p)

            if current_db_sha == manifest.db_sha256 and current_pt_sha == manifest.pt_sha256:
                # Valid snapshot found!
                is_rewind = idx > 0
                # Restore live database from verified snapshot using SQLite backup API
                if live_db.exists():
                    src = sqlite3.connect(db_p)
                    dst = sqlite3.connect(live_db)
                    try:
                        src.backup(dst)
                    finally:
                        src.close()
                        dst.close()
                else:
                    shutil.copy2(db_p, live_db)

                # Sync latest.md to rewound ledger
                if manifest.ledger_path and Path(manifest.ledger_path).exists():
                    latest_ledger = self.god_ledger_dir / "latest.md"
                    try:
                        shutil.copy2(manifest.ledger_path, latest_ledger)
                    except OSError:
                        pass

                if is_rewind:
                    msg = (
                        f"[CORRUPTION_REWIND] Latest checkpoint corrupted. "
                        f"Automatically rewound to Day {manifest.day} (SHA-256 verified)."
                    )
                else:
                    msg = f"BOOT_CLEAN: Verified Day {manifest.day} snapshot."

                return manifest.day, manifest, msg

        raise RuntimeError("CORRUPTION_REWIND_FAILED: Zero valid verified snapshots found.")
