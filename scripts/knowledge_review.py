#!/usr/bin/env python3
# ruff: noqa: E402
"""
scripts/knowledge_review.py

Fast 3-Stage Pre-Merge Review CLI for Knowledge Foundry.

Audits staged .json packs against each other and against the live SQLite world_library.
Prints formatted rich summary tables and returns non-zero exit code on any hard block.
"""

from __future__ import annotations

import argparse
import json
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


def load_library_from_db(db_path: Path) -> list[dict[str, Any]]:
    """Loads existing world_library entries from SQLite if database exists."""
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

        cursor.execute(
            "SELECT entry_id, topic, title, summary, author_id, author_proficiency, "
            "skill_bonus, is_scripture, read_count, created_tick FROM world_library;"
        )
        rows = cursor.fetchall()
        entries = []
        for r in rows:
            entries.append(
                {
                    "entry_id": r[0],
                    "subject": r[1],
                    "topic": r[1],
                    "fact_key": r[1],
                    "title": r[2],
                    "summary": r[3],
                    "body": r[3],
                    "author": r[4],
                    "author_id": r[4],
                    "author_type": "DIVINE" if r[7] == 1 else "MORTAL",
                    "mechanical_effects": {"skill_bonus": float(r[6])},
                    "supersedes": [],
                    "distinct_from": [],
                }
            )
        conn.close()
        return entries
    except Exception as ex:
        print(f"Warning: Could not read existing library from {db_path}: {ex}", file=sys.stderr)
        return []


def collect_staged_packs(knowledge_dir: Path) -> list[Path]:
    """Collects all .json files in knowledge_dir, skipping directories starting with '_'."""
    packs = []
    if not knowledge_dir.exists():
        return packs

    for p in sorted(knowledge_dir.rglob("*.json")):
        # Skip if any parent part relative to knowledge_dir starts with '_'
        rel_parts = p.relative_to(knowledge_dir).parts
        if any(part.startswith("_") for part in rel_parts[:-1]):
            continue
        packs.append(p)
    return packs


def main() -> int:
    parser = argparse.ArgumentParser(description="Gaia v4.0 Knowledge Foundry Pre-Merge Review CLI")
    parser.add_argument(
        "--knowledge-dir",
        type=Path,
        default=Path("data/knowledge"),
        help="Root staged knowledge directory (default: data/knowledge)",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("data/civilization.db"),
        help="Path to SQLite civilization database (default: data/civilization.db)",
    )
    parser.add_argument(
        "--json-report",
        type=Path,
        default=None,
        help="Optional path to output raw JSON report",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on near-duplicate warnings (0.78-0.87 similarity)",
    )

    args = parser.parse_args()
    console = Console()

    console.print(
        Panel.fit(
            "[bold cyan]Gaia v4.0 Knowledge Foundry — 3-Stage Pre-Merge Review[/bold cyan]\n"
            f"[dim]Knowledge Dir: {args.knowledge_dir} | DB: {args.db_path}[/dim]",
            border_style="cyan",
        )
    )

    packs = collect_staged_packs(args.knowledge_dir)
    if not packs:
        console.print(f"[yellow]No staged packs found in {args.knowledge_dir}[/yellow]")
        return 0

    existing_entries = load_library_from_db(args.db_path)
    engine = DeduplicationEngine(existing_entries)

    report = engine.audit_packs(packs, strict_near_dupes=args.strict)

    # 1. Audited Packs Table
    packs_table = Table(title="Audited Staged Packs", border_style="dim")
    packs_table.add_column("Pack File", style="cyan")
    packs_table.add_column("Entries", justify="right")
    packs_table.add_column("Status", justify="center")

    for p in packs:
        # Determine if this file had hard errors
        has_fail = any(f.get("file") == str(p) for f in report.hard_fails)
        has_dup = any(
            d.get("file") == str(p)
            for d in (
                report.hard_duplicates + report.lexical_duplicates + report.semantic_duplicates
            )
        )
        if has_fail:
            status = "[bold red]SCHEMA FAIL[/bold red]"
        elif has_dup:
            status = "[bold red]DUPLICATE[/bold red]"
        else:
            status = "[bold green]PASS[/bold green]"

        try:
            with open(p, encoding="utf-8") as f:
                cnt = len(json.load(f))
        except Exception:
            cnt = 0
        packs_table.add_row(str(p.relative_to(args.knowledge_dir)), str(cnt), status)

    console.print(packs_table)

    # 2. Hard Blocks Table
    all_blocks = (
        report.hard_fails
        + report.hard_duplicates
        + report.lexical_duplicates
        + report.semantic_duplicates
    )
    if all_blocks:
        blocks_table = Table(
            title="[bold red]Hard Blocking Violations[/bold red]", border_style="red"
        )
        blocks_table.add_column("Stage", justify="center", style="bold red")
        blocks_table.add_column("Entry ID / File", style="yellow")
        blocks_table.add_column("Conflict With", style="magenta")
        blocks_table.add_column("Reason", style="white")

        for b in all_blocks:
            stage_str = f"Stage {b.get('stage', 0)}"
            entry_str = b.get("entry_id") or Path(b.get("file", "")).name
            conflict_str = b.get("conflict_with") or "-"
            reason_str = b.get("reason", "")
            blocks_table.add_row(stage_str, entry_str, conflict_str, reason_str)

        console.print(blocks_table)

    # 3. Near Duplicates Table
    if report.near_duplicates:
        near_table = Table(
            title="[bold yellow]Near-Duplicate Review Warnings (0.78-0.87)[/bold yellow]",
            border_style="yellow",
        )

        near_table.add_column("Entry ID", style="cyan")
        near_table.add_column("Similar To", style="magenta")
        near_table.add_column("Cosine", justify="right", style="bold yellow")
        near_table.add_column("Title Comparison", style="dim")

        for nd in report.near_duplicates:
            near_table.add_row(
                nd["entry_id"],
                nd["conflict_with"],
                f"{nd['similarity']:.1%}",
                f"'{nd['title_a'][:32]}' vs '{nd['title_b'][:32]}'",
            )

        console.print(near_table)

    # 4. Conflicts Table
    if report.conflicts:
        conf_table = Table(
            title="[bold red]Opposing Mechanical Effect Conflicts[/bold red]",
            border_style="red",
        )
        conf_table.add_column("Entry ID", style="cyan")
        conf_table.add_column("Opposing Entry", style="magenta")
        conf_table.add_column("Effect Key", style="yellow")
        conf_table.add_column("Values", style="bold red")

        for cf in report.conflicts:
            conf_table.add_row(
                cf["entry_id"],
                cf["conflict_with"],
                cf["effect_key"],
                f"{cf['val_a']:+.2f} vs {cf['val_b']:+.2f}",
            )

        console.print(conf_table)

    # Summary Panel
    verdict_text = (
        "[bold green]REVIEW PASSED — ALL PACKS READY FOR MERGE[/bold green]"
        if report.is_clean
        else "[bold red]REVIEW BLOCKED — RESOLVE HARD FAILURES / DUPLICATES[/bold red]"
    )

    summary_panel = Panel(
        f"[bold]Packs Audited:[/bold] {report.total_packs}\n"
        f"[bold]Total Entries:[/bold] {report.total_entries}\n"
        f"[bold]Passed Entries:[/bold] {report.passed_entries}\n"
        f"[bold]Hard Blocks:[/bold] {len(all_blocks)}\n"
        f"[bold]Near Duplicates:[/bold] {len(report.near_duplicates)}\n"
        f"[bold]Conflicts:[/bold] {len(report.conflicts)}\n"
        f"[bold]Duration:[/bold] {report.duration_ms:.1f} ms\n\n"
        f"{verdict_text}",
        title="Review Audit Summary",
        border_style="green" if report.is_clean else "red",
    )
    console.print(summary_panel)

    if args.json_report:
        report_data = {
            "is_clean": report.is_clean,
            "total_packs": report.total_packs,
            "total_entries": report.total_entries,
            "passed_entries": report.passed_entries,
            "hard_fails": report.hard_fails,
            "hard_duplicates": report.hard_duplicates,
            "lexical_duplicates": report.lexical_duplicates,
            "semantic_duplicates": report.semantic_duplicates,
            "near_duplicates": report.near_duplicates,
            "conflicts": report.conflicts,
            "duration_ms": report.duration_ms,
        }
        with open(args.json_report, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)
        console.print(f"[dim]JSON report written to {args.json_report}[/dim]")

    return 0 if report.is_clean else 1


if __name__ == "__main__":
    sys.exit(main())
