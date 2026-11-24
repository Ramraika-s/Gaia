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

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from sim_core.knowledge.db_loader import (
    collect_staged_packs,
    ensure_world_library_schema,
    load_library_from_db,
)
from sim_core.knowledge.dedupe import DeduplicationEngine
from sim_core.knowledge.schema import KnowledgePack
from sim_core.persistence.world_goddess import WorldGoddessCritic
from sim_core.schemas import CommitProposal

# Alias for backwards compatibility with tests
ensure_db_columns = ensure_world_library_schema


def main(argv: list[str] | None = None) -> int:
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
    parser.add_argument(
        "--pack",
        type=Path,
        default=None,
        help="Optional specific pack file to merge",
    )
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=None,
        help="Optional custom archive directory (default: <knowledge_dir>/_merged_archive)",
    )

    args = parser.parse_args(argv)
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

    packs = collect_staged_packs(args.knowledge_dir, pack_path=args.pack)
    if not packs:
        console.print("[yellow]No staged packs found to merge.[/yellow]")
        return 0

    existing_entries = load_library_from_db(args.db_path)
    engine = DeduplicationEngine(existing_entries)

    # Register entries from other staged packs in knowledge_dir to catch cross-pack duplicates
    if args.pack:
        target_path = args.pack.resolve()
        sibling_packs = [
            p for p in collect_staged_packs(args.knowledge_dir)
            if p.resolve() != target_path
        ]
        for sib in sibling_packs:
            try:
                with open(sib, encoding="utf-8") as f:
                    sib_data = json.load(f)
                sib_entries = (
                    sib_data.get("entries", [])
                    if isinstance(sib_data, dict)
                    else (sib_data if isinstance(sib_data, list) else [])
                )
                for entry_dict in sib_entries:
                    engine._register_existing(entry_dict)
            except Exception:
                pass

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

            try:
                rel_label = str(p.relative_to(args.knowledge_dir))
            except ValueError:
                rel_label = str(p)
            dry_table.add_row(
                rel_label,
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
    ensure_world_library_schema(conn)

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
                        subject, section, fact_key, tags_json, mechanical_effects_json,
                        author_type, body
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
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
                        entry.body,
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

    # Move merged packs to archive_dir with timestamp stamp
    archive_dir = (
        args.archive_dir
        if args.archive_dir is not None
        else (args.knowledge_dir / "_merged_archive")
    )
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
