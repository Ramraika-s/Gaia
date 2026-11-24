"""
sim_core/knowledge/db_loader.py
Single Authoritative Knowledge Database Loader & Pack Collector for Gaia v4.0.
Used by scripts/knowledge_review.py, scripts/knowledge_merge.py, and scripts/celestial_ingest.py.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


def ensure_world_library_schema(conn: sqlite3.Connection) -> None:
    """Ensures world_library table and all schema columns exist idempotently."""
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
        author_type TEXT DEFAULT 'MORTAL',
        body TEXT
    );
    """)

    cursor.execute("PRAGMA table_info(world_library);")
    existing_cols = {row[1] for row in cursor.fetchall()}

    new_cols = [
        ("subject", "TEXT"),
        ("section", "TEXT"),
        ("fact_key", "TEXT"),
        ("tags_json", "TEXT"),
        ("mechanical_effects_json", "TEXT"),
        ("author_type", "TEXT DEFAULT 'MORTAL'"),
        ("body", "TEXT"),
    ]
    for col_name, col_type in new_cols:
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE world_library ADD COLUMN {col_name} {col_type};")

    conn.commit()


def load_library_from_db(db_path: Path) -> list[dict[str, Any]]:
    """
    Dynamically inspects PRAGMA table_info(world_library) and loads ALL fields
    including body (falling back to summary if body is NULL/empty), tags, mechanical_effects,
    subject, section, fact_key, and author_type.
    """
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
        entries: list[dict[str, Any]] = []
        for r in rows:
            d = dict(zip(cols, r, strict=False))
            raw_body = d.get("body")
            raw_summary = d.get("summary", "")
            body = raw_body if raw_body else raw_summary

            raw_tags = d.get("tags_json")
            tags: list[str] = []
            if raw_tags:
                try:
                    tags = json.loads(raw_tags)
                except (json.JSONDecodeError, TypeError):
                    tags = []

            raw_effects = d.get("mechanical_effects_json")
            effects: dict[str, float] = {}
            if raw_effects:
                try:
                    effects = json.loads(raw_effects)
                except (json.JSONDecodeError, TypeError):
                    effects = {}
            elif "skill_bonus" in d:
                effects = {"skill_bonus": float(d["skill_bonus"])}

            entry_dict: dict[str, Any] = {
                "entry_id": d["entry_id"],
                "subject": d.get("subject") or d.get("topic", "unknown"),
                "topic": d.get("topic", "unknown"),
                "section": d.get("section") or "General",
                "target_section": d.get("section") or "General",
                "fact_key": d.get("fact_key") or d.get("topic", "unknown"),
                "title": d.get("title", ""),
                "summary": raw_summary,
                "body": body,
                "author": d.get("author_id", "system"),
                "author_id": d.get("author_id", "system"),
                "author_type": d.get("author_type", "MORTAL"),
                "author_proficiency": float(d.get("author_proficiency", 1.0)),
                "skill_bonus": float(d.get("skill_bonus", 0.08)),
                "is_scripture": bool(d.get("is_scripture", 0)),
                "read_count": int(d.get("read_count", 0)),
                "created_tick": int(d.get("created_tick", 0)),
                "tags": tags,
                "mechanical_effects": effects,
                "supersedes": [],
                "distinct_from": [],
            }
            entries.append(entry_dict)
        conn.close()
        return entries
    except Exception as ex:
        print(f"Warning: Could not read library from {db_path}: {ex}", file=sys.stderr)
        return []


def collect_staged_packs(
    knowledge_dir: Path, pack_path: Path | None = None
) -> list[Path]:
    """
    If pack_path is provided, validates and returns [pack_path].
    Otherwise collects all .json files under knowledge_dir skipping directories starting with '_'.
    """
    if pack_path is not None:
        p = Path(pack_path)
        if not p.exists():
            raise FileNotFoundError(f"Specified pack file not found: {p}")
        return [p]

    packs: list[Path] = []
    if not knowledge_dir.exists():
        return packs

    for p in sorted(knowledge_dir.rglob("*.json")):
        rel_parts = p.relative_to(knowledge_dir).parts
        if any(part.startswith("_") for part in rel_parts[:-1]):
            continue
        packs.append(p)
    return packs


def count_pack_entries(pack_path: Path) -> int:
    """
    Correctly counts entries for BOTH list-format JSON ([...]) and
    dict-format JSON ({"pack_id": ..., "entries": [...]}).
    """
    if not pack_path.exists():
        return 0
    try:
        with open(pack_path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return len(data)
        elif isinstance(data, dict):
            entries = data.get("entries")
            if isinstance(entries, list):
                return len(entries)
            return 0
        return 0
    except (json.JSONDecodeError, OSError):
        return 0
