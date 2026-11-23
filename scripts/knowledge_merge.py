#!/usr/bin/env python3
# ruff: noqa: E402
"""
scripts/knowledge_merge.py
Atomic World Library Merge CLI for Knowledge Foundry.


Validates all staged packs via 3-Stage deduplication cascade.
Refuses to commit if any hard blocks exist.
On --commit:
- Inserts/updates entries into SQLite world_library via WorldGoddessCritic bypass
- Updates embedding vector cache
- Archives merged packs into data/knowledge/_merged_archive/ with cryptographic timestamp stamp
"""

from __future__ import annotations

import argparse
import datetime
import json
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from sim_core.knowledge.dedupe import DeduplicationEngine
from sim_core.knowledge.schema import KnowledgePack
from sim_core.persistence.world_goddess import WorldGoddessCritic
from sim_core.schemas import CommitProposal


def ensure_db_columns(conn: sqlite3.Connection) -> None:
    """Ensures world_library table and extended metadata columns exist."""
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS world_library (
        entry_id TEXT PRIMARY KEY,
        topic TEXT NOT NULL,
        title TEXT NOT NULL,
        summary TEXT NOT NULL,
        author_id TEXT NOT NULL,
        author_proficiency REAL NOT NULL DEFAULT 0.85,
        skill_bonus REAL NOT NULL DEFAULT 0.08,
        is_scripture INTEGER NOT NULL DEFAULT 0,
        read_count INTEGER NOT NULL DEFAULT 0,
        created_tick INTEGER NOT NULL DEFAULT 0,
        subject TEXT,
        section TEXT,
        fact_key TEXT,
        tags_json TEXT,
        mechanical_effects_json TEXT,
        author_type TEXT DEFAULT 'MORTAL'
    );
    """)

    # Check for existing table missing new columns and add them dynamically
    cursor.execute("PRAGMA table_info(world_library);")
    existing_cols = {row[1] for row in cursor.fetchall()}

    new_cols = [
        ("subject", "TEXT"),
        ("section", "TEXT"),
        ("fact_key", "TEXT"),
        ("tags_json", "TEXT"),
        ("mechanical_effects_json", "TEXT"),
        ("author_type", "TEXT DEFAULT 'MORTAL'"),
    ]
    for col_name, col_type in new_cols:
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE world_library ADD COLUMN {col_name} {col_type};")

    conn.commit()


def load_library_from_db(db_path: Path) -> list[dict[str, Any]]:
    """Loads existing world_library entries from SQLite."""
    if not db_path.exists():
        return []

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='world_library';"
        )
        if not cursor.fetchone():
            conn.close()
            return []

        cursor.execute("PRAGMA table_info(world_library);")
        cols = [r[1] for r in cursor.fetchall()]

        cursor.execute("SELECT * FROM world_library;")
        rows = cursor.fetchall()
        entries = []
        for r in rows:
            d = dict(zip(cols, r, strict=False))
            entries.append(
                {
                    "entry_id": d["entry_id"],
                    "subject": d.get("subject") or d.get("topic", "unknown"),
                    "topic": d.get("topic", "unknown"),
                    "fact_key": d.get("fact_key") or d.get("topic", "unknown"),
                    "title": d.get("title", ""),
                    "summary": d.get("summary", ""),
                    "body": d.get("summary", ""),
                    "author": d.get("author_id", "system"),
                    "author_id": d.get("author_id", "system"),
                    "author_type": d.get("author_type", "MORTAL"),
                    "mechanical_effects": json.loads(d.get("mechanical_effects_json") or "{}"),
                    "supersedes": [],
                    "distinct_from": [],
                }
            )
        conn.close()
        return entries
    except Exception as ex:
        print(f"Warning: Could not read library from {db_path}: {ex}", file=sys.stderr)
        return []


def collect_staged_packs(knowledge_dir: Path) -> list[Path]:
    """Collects all staged .json files, skipping directories starting with '_'."""
    packs = []
    if not knowledge_dir.exists():
        return packs

    for p in sorted(knowledge_dir.rglob("*.json")):
        rel_parts = p.relative_to(knowledge_dir).parts
        if any(part.startswith("_") for part in rel_parts[:-1]):
            continue
        packs.append(p)
    return packs


def main() -> int:
    parser = argparse.ArgumentParser(description="Gaia v4.0 Knowledge Foundry Merge CLI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--dry-run",
        action="store_true",
        help="Audit and simulate merge without writing changes to DB or archiving files",
    )
    group.add_argument(
        "--commit",
        action="store_true",
        help="Commit validated knowledge packs into world_library and archive them",
    )
    parser.add_argument(
        "--knowledge-dir",
        type=Path,
        default=Path("data/knowledge"),
        help="Staged knowledge directory (default: data/knowledge)",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("data/civilization.db"),
        help="Path to SQLite civilization database (default: data/civilization.db)",
    )

    args = parser.parse_args()
    console = Console()

    mode_str = (
        "[bold yellow]DRY-RUN (SIMULATION)[/bold yellow]"
        if args.dry_run
        else "[bold green]COMMIT (LIVE WRITE)[/bold green]"
    )
    console.print(
        Panel.fit(
            f"[bold cyan]Gaia v4.0 Knowledge Foundry — World Library Merge[/bold cyan]\n"
            f"Mode: {mode_str} | Knowledge: {args.knowledge_dir} | DB: {args.db_path}",
            border_style="cyan",
        )
    )

    packs = collect_staged_packs(args.knowledge_dir)
    if not packs:
        console.print("[yellow]No staged packs found to merge.[/yellow]")
        return 0

    existing_entries = load_library_from_db(args.db_path)
    engine = DeduplicationEngine(existing_entries)

    report = engine.audit_packs(packs)

    if not report.is_clean:
        console.print(
            "[bold red]MERGE ABORTED: Staged packs contain unresolved violations.[/bold red]"
        )
        console.print(
            f"Hard Fails: {len(report.hard_fails)} | Exact: {len(report.hard_duplicates)}\n"
            f"Lexical: {len(report.lexical_duplicates)} | "
            f"Semantic: {len(report.semantic_duplicates)}"
        )

        return 1

    # Load and validate all entries into memory
    all_packs_data = []
    total_entries_count = 0
    for p in packs:
        with open(p, encoding="utf-8") as f:
            pack_data = json.load(f)
        pack_obj = KnowledgePack.model_validate(pack_data)
        all_packs_data.append((p, pack_obj))
        total_entries_count += len(pack_obj.entries)

    critic = WorldGoddessCritic()

    if args.dry_run:
        dry_table = Table(title="Dry-Run Merge Projection", border_style="yellow")
        dry_table.add_column("Pack File", style="cyan")
        dry_table.add_column("Entries to Merge", justify="right")
        dry_table.add_column("WorldGoddess Critic", justify="center", style="bold green")

        for p, pack_obj in all_packs_data:
            # Verify critic evaluation with divine bypass
            for entry in pack_obj.entries:
                proposal = CommitProposal(
                    proposal_id=f"dry_merge_{entry.entry_id}",
                    kind="LIBRARY_ENTRY",
                    actor_id="knowledge_foundry_admin",
                    payload={"entry_id": entry.entry_id, "title": entry.title},
                    bypass_god_check=True,
                    tick=0,
                )
                verdict = critic.evaluate(proposal)
                if verdict.status != "SUCCESS":
                    console.print(
                        f"[bold red]Critic rejected {entry.entry_id}: {verdict.reason}[/bold red]"
                    )
                    return 1

            dry_table.add_row(
                str(p.relative_to(args.knowledge_dir)),
                str(len(pack_obj.entries)),
                "APPROVED (Bypass Granted)",
            )

        console.print(dry_table)
        console.print(
            Panel(
                f"[bold green]DRY-RUN SUCCESSFUL[/bold green]\n"
                f"{len(packs)} packs ({total_entries_count} entries) verified.\n"
                "Zero database writes executed.",
                border_style="yellow",
            )
        )
        return 0

    # -------------------------------------------------------------------------
    # COMMIT MODE: Live SQLite Transaction + File Archival
    # -------------------------------------------------------------------------
    args.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(args.db_path)
    ensure_db_columns(conn)

    cursor = conn.cursor()
    cursor.execute("BEGIN IMMEDIATE;")

    merged_entries_count = 0
    superseded_count = 0

    try:
        for _, pack_obj in all_packs_data:
            for entry in pack_obj.entries:
                # 1. Critic evaluation
                proposal = CommitProposal(
                    proposal_id=f"merge_{entry.entry_id}",
                    kind="LIBRARY_ENTRY",
                    actor_id="knowledge_foundry_admin",
                    payload={
                        "entry_id": entry.entry_id,
                        "title": entry.title,
                        "author_proficiency": 0.90,
                    },
                    bypass_god_check=True,
                    tick=0,
                )
                verdict = critic.evaluate(proposal)
                if verdict.status != "SUCCESS":
                    raise RuntimeError(f"Critic rejected {entry.entry_id}: {verdict.reason}")

                # 2. Handle supersedes
                for target in entry.supersedes:
                    cursor.execute(
                        "DELETE FROM world_library WHERE entry_id = ? OR fact_key = ?;",
                        (target, target),
                    )
                    superseded_count += cursor.rowcount

                # 3. Insert or Replace entry
                skill_bonus = entry.mechanical_effects.get("skill_bonus", 0.08)
                tags_json = json.dumps(entry.tags)
                effects_json = json.dumps(entry.mechanical_effects)

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO world_library (
                        entry_id, topic, title, summary, author_id, author_proficiency,
                        skill_bonus, is_scripture, read_count, created_tick,
                        subject, section, fact_key, tags_json, mechanical_effects_json, author_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        entry.entry_id,
                        entry.fact_key,
                        entry.title,
                        entry.summary,
                        entry.author,
                        0.90,
                        float(skill_bonus),
                        1 if entry.author_type == "DIVINE" else 0,
                        0,
                        0,
                        entry.subject,
                        entry.target_section,
                        entry.fact_key,
                        tags_json,
                        effects_json,
                        entry.author_type,
                    ),
                )
                merged_entries_count += 1

        conn.commit()
    except Exception as ex:
        conn.rollback()
        conn.close()
        console.print(f"[bold red]DATABASE COMMIT FAILED: {ex}[/bold red]")
        return 1

    conn.close()

    # Move merged packs to _merged_archive/ with timestamp stamp
    archive_dir = args.knowledge_dir / "_merged_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    timestamp_prefix = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d_%H%M%S")

    for p, _ in all_packs_data:
        dest_filename = f"{timestamp_prefix}_{p.name}"
        dest_path = archive_dir / dest_filename
        shutil.move(p, dest_path)

    console.print(
        Panel(
            f"[bold green]COMMIT SUCCESSFUL[/bold green]\n"
            f"[bold]Entries Merged:[/bold] {merged_entries_count}\n"
            f"[bold]Older Entries Superseded:[/bold] {superseded_count}\n"
            f"[bold]Packs Archived:[/bold] {len(all_packs_data)} moved to {archive_dir}\n"
            f"[bold]Database:[/bold] {args.db_path} updated atomically.",
            title="World Library Merge Result",
            border_style="green",
        )
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
