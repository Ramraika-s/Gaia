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
    count_pack_entries,
    load_library_from_db,
)
from sim_core.knowledge.dedupe import DeduplicationEngine


def main(argv: list[str] | None = None) -> int:
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
    parser.add_argument(
        "--pack",
        type=Path,
        default=None,
        help="Optional specific pack file to review",
    )

    args = parser.parse_args(argv)
    console = Console()

    console.print(
        Panel.fit(
            "[bold cyan]Gaia v4.0 Knowledge Foundry — 3-Stage Pre-Merge Review[/bold cyan]\n"
            f"[dim]Knowledge Dir: {args.knowledge_dir} | DB: {args.db_path}[/dim]",
            border_style="cyan",
        )
    )

    packs = collect_staged_packs(args.knowledge_dir, pack_path=args.pack)
    if not packs:
        console.print(f"[yellow]No staged packs found in {args.knowledge_dir}[/yellow]")
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

        cnt = count_pack_entries(p)
        try:
            rel_label = str(p.relative_to(args.knowledge_dir))
        except ValueError:
            rel_label = str(p)
        packs_table.add_row(rel_label, str(cnt), status)

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
