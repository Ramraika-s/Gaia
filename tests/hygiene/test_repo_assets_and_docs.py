"""
tests/hygiene/test_repo_assets_and_docs.py
Tests repository asset parity, orphan deletion, single-source constants, and doc link integrity.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_asset_manifest_parity() -> None:
    """100% of res:// paths listed in ASSET_MANIFEST.json must resolve to existing files on disk."""
    manifest_path = REPO_ROOT / "godot_client" / "assets" / "ASSET_MANIFEST.json"
    assert manifest_path.is_file(), f"Manifest file missing: {manifest_path}"

    with open(manifest_path, encoding="utf-8") as f:
        manifest: dict[str, Any] = json.load(f)

    assert manifest.get("version") == "4.0.0", (
        f"Manifest version expected 4.0.0, got {manifest.get('version')}"
    )

    checked_paths = 0

    def check_res_path(val: Any) -> None:
        nonlocal checked_paths
        if isinstance(val, str) and val.startswith("res://"):
            rel_part = val.removeprefix("res://")
            disk_path = REPO_ROOT / "godot_client" / rel_part
            assert disk_path.exists(), (
                f"Path in ASSET_MANIFEST.json missing on disk: {val} -> {disk_path}"
            )
            checked_paths += 1
        elif isinstance(val, dict):
            for v in val.values():
                check_res_path(v)
        elif isinstance(val, list):
            for v in val:
                check_res_path(v)

    check_res_path(manifest)
    assert checked_paths >= 15, f"Expected at least 15 verified asset paths, found {checked_paths}"


def test_orphaned_assets_deleted() -> None:
    """Confirms deleted orphan files and directories no longer exist in repository."""
    forbidden_paths = [
        REPO_ROOT / "godot_client" / "demo",
        REPO_ROOT / "godot_client" / "scenes" / "landmarks" / "world_goddess_sanctum.tscn",
        REPO_ROOT / "godot_client" / "assets" / "ui" / "portraits",
        REPO_ROOT / "godot_client" / "assets" / "audio" / "voice",
        REPO_ROOT / "godot_client" / "shaders" / "stylized_toon_season.gdshader",
        REPO_ROOT / ".cache" / "knowledge_foundry",
    ]

    for p in forbidden_paths:
        assert not p.exists(), f"Forbidden orphaned path should be deleted: {p}"


def test_single_source_constant_reconciliation() -> None:
    """Verifies DEFAULT_DEITY_NAMES and SETTLEMENT_TIER_REQUIREMENTS match consumers 1:1."""
    from sim_core.config import DEFAULT_DEITY_NAMES, SETTLEMENT_TIER_REQUIREMENTS
    from sim_core.divine.hierarchy import DivineHierarchyManager
    from sim_core.society.borders import TIER_THRESHOLDS

    # 1. Deity names match
    manager = DivineHierarchyManager()
    for slot, expected_name in DEFAULT_DEITY_NAMES.items():
        assert slot in manager.entities, f"Deity slot {slot} missing in DivineHierarchyManager"
        bestowed = manager.entities[slot].bestowed_name
        assert bestowed == expected_name, (
            f"Deity slot {slot} has name {bestowed}, expected {expected_name}"
        )

    # 2. Settlement tier thresholds match
    assert TIER_THRESHOLDS is SETTLEMENT_TIER_REQUIREMENTS, (
        "borders.TIER_THRESHOLDS must be single-sourced alias to SETTLEMENT_TIER_REQUIREMENTS"
    )

    for tier in ("VILLAGE", "TOWN", "CITY", "STATE", "NATION"):
        assert tier in SETTLEMENT_TIER_REQUIREMENTS, (
            f"Tier {tier} missing in SETTLEMENT_TIER_REQUIREMENTS"
        )
        reqs = SETTLEMENT_TIER_REQUIREMENTS[tier]
        assert "min_pop" in reqs
        assert "min_parcels" in reqs
        assert "min_treasury" in reqs


def test_markdown_relative_links_integrity() -> None:
    """Verifies that all relative file links in core documentation resolve to real files."""
    doc_files = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "AGENTS.md",
        REPO_ROOT / "docs" / "INDEX.md",
    ] + list((REPO_ROOT / "docs").rglob("*.md"))

    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    checked_links = 0

    for doc in doc_files:
        content = doc.read_text(encoding="utf-8")
        for match in link_pattern.finditer(content):
            raw_target = match.group(2).strip()

            if raw_target.startswith(("http://", "https://", "mailto:", "#")):
                continue

            target_clean = raw_target.split("#")[0].split("?")[0]
            if not target_clean:
                continue

            if target_clean.startswith("file://"):
                resolved_target = Path(target_clean.removeprefix("file://"))
            elif target_clean.startswith("/"):
                resolved_target = Path(target_clean)
            else:
                resolved_target = (doc.parent / target_clean).resolve()

            assert resolved_target.exists(), (
                f"Broken markdown link in {doc.relative_to(REPO_ROOT)}: "
                f"'{raw_target}' resolves to non-existent path '{resolved_target}'"
            )
            checked_links += 1

    assert checked_links >= 40, (
        f"Expected at least 40 verified markdown links, found {checked_links}"
    )


@pytest.mark.benchmark
@pytest.mark.slow
def test_neural_benchmark_interface() -> None:
    """Verifies that bench_tensors runs both 3-tier and legacy 2-tier benchmarks without error."""
    from sim_core.tools.bench_tensors import run_benchmark

    m_3tier = run_benchmark(num_agents=2048, num_steps=2, legacy_2tier=False)
    assert m_3tier["num_agents"] == 2048.0
    assert m_3tier["avg_ms"] > 0.0
    assert m_3tier["ram_mb"] < 250.0

    m_legacy = run_benchmark(num_agents=2048, num_steps=2, legacy_2tier=True)
    assert m_legacy["num_agents"] == 2048.0
    assert m_legacy["avg_ms"] > 0.0
    assert m_legacy["ram_mb"] < 250.0
