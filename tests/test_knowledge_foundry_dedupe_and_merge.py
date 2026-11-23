"""
tests/test_knowledge_foundry_dedupe_and_merge.py
Acceptance tests for Gaia v4.0 — Sprint 0:
1. Knowledge Foundry Schema, Entry Cap (<=30), and Anachronism Guardrails.
2. 3-Stage Cascaded Deduplication (Exact/Normalized Hash, Lexical, Vectors, Conflicts).
3. Supersedes and Distinct-From exemptions.
4. CLI Merge Tool: Dry-Run (zero DB writes) vs. Commit (SQLite WAL + Archive).
5. Mortal Book Petitions: Deduplication rejection & 5-Daughter Governance Pipeline.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from sim_core.knowledge.dedupe import (
    DeduplicationEngine,
)
from sim_core.knowledge.schema import (
    KnowledgeEntry,
    KnowledgePack,
    validate_anachronisms,
)
from sim_core.society.library import (
    OBJECTION_WINDOW_TICKS,
    TwoBookGovernanceEngine,
)


def _make_sample_entry(
    entry_id: str = "tactics_sample_001",
    subject: str = "tactics_and_warfare",
    target_section: str = "military_tactics",
    fact_key: str = "tactics_and_warfare.siege.murder_holes",
    title: str = "Murder Holes and Transverse Gate Defense",
    summary: str = "Engineering overhead apertures to drop heavy stones onto siege crews.",
    body: str = (
        "When enemy forces breach outer wooden gates, they enter an enclosed vaulted passageway "
        "before the inner portcullis. Overhead ceiling slots allow defenders to drop heavy stones."
    ),
    author: str = "Captain Vane",
    era_tier: int = 1,
    tags: list[str] | None = None,
    mechanical_effects: dict[str, float] | None = None,
    supersedes: list[str] | None = None,
    distinct_from: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "entry_id": entry_id,
        "subject": subject,
        "target_section": target_section,
        "fact_key": fact_key,
        "title": title,
        "summary": summary,
        "body": body,
        "author": author,
        "author_type": "MORTAL",
        "era_tier": era_tier,
        "tags": tags or ["fortification", "gate_defense"],
        "prerequisites": [],
        "mechanical_effects": mechanical_effects or {"defense_bonus": 0.15},
        "supersedes": supersedes or [],
        "distinct_from": distinct_from or [],
    }


# =============================================================================
# 1. Schema Validation, Entry Cap & Anachronism Guardrails
# =============================================================================


def test_schema_valid_pack():
    entry_dict = _make_sample_entry()
    pack = KnowledgePack.model_validate([entry_dict])
    assert len(pack.entries) == 1
    assert pack.entries[0].entry_id == "tactics_sample_001"
    assert pack.entries[0].subject == "tactics_and_warfare"


def test_schema_rejects_greater_than_30_entries():
    entries = [
        _make_sample_entry(
            entry_id=f"tactics_entry_{i:03d}", fact_key=f"tactics_and_warfare.siege.k_{i}"
        )
        for i in range(31)
    ]
    with pytest.raises(ValidationError) as exc_info:
        KnowledgePack.model_validate(entries)
    assert "at most 30" in str(exc_info.value) or "30" in str(exc_info.value)


def test_schema_rejects_anachronisms():
    # 1. Modern term in summary
    bad_summary = _make_sample_entry(
        summary="Using electricity to shock advancing infantry at the gate."
    )
    with pytest.raises(ValidationError) as exc:
        KnowledgeEntry.model_validate(bad_summary)
    assert "electricity" in str(exc.value)

    # 2. Modern term in title
    bad_title = _make_sample_entry(title="Deploying Smartphone Telecommunications Across Bastions")
    with pytest.raises(ValidationError) as exc:
        KnowledgeEntry.model_validate(bad_title)
    assert "smartphone" in str(exc.value)

    # 3. Modern term in body
    bad_body = _make_sample_entry(
        body="This defensive doctrine was first codified on the medieval Wikipedia page."
    )
    with pytest.raises(ValidationError) as exc:
        KnowledgeEntry.model_validate(bad_body)
    assert "wikipedia" in str(exc.value)

    # 4. Modern term in tags
    bad_tag = _make_sample_entry(tags=["fortification", "nuclear"])
    with pytest.raises(ValidationError) as exc:
        KnowledgeEntry.model_validate(bad_tag)
    assert "nuclear" in str(exc.value)


def test_anachronism_function_helper():
    assert validate_anachronisms("We harness clean solar electricity.") == "electricity"
    assert validate_anachronisms("A stone masonry arch with lime mortar.") is None


# =============================================================================
# 2. Stage 1: Exact & Normalized Hash Duplicate Detection
# =============================================================================


def test_stage_1_exact_and_normalized_duplicates(tmp_path: Path):
    pack_a_path = tmp_path / "pack_a.json"
    pack_b_path = tmp_path / "pack_b.json"

    entry_1 = _make_sample_entry(
        entry_id="entry_unique_001", fact_key="tactics_and_warfare.siege.concept_a"
    )
    entry_2 = _make_sample_entry(
        entry_id="entry_unique_001", fact_key="tactics_and_warfare.siege.concept_b"
    )  # duplicate ID

    with open(pack_a_path, "w", encoding="utf-8") as f:
        json.dump([entry_1], f)
    with open(pack_b_path, "w", encoding="utf-8") as f:
        json.dump([entry_2], f)

    engine = DeduplicationEngine()
    report = engine.audit_packs([pack_a_path, pack_b_path])
    assert not report.is_clean
    assert len(report.hard_duplicates) >= 1
    assert any("entry_id collision" in d["reason"] for d in report.hard_duplicates)


def test_stage_1_normalized_text_hash_collision(tmp_path: Path):
    pack_a = tmp_path / "pack_a.json"
    pack_b = tmp_path / "pack_b.json"

    # Same text, differing in punctuation and capitalization
    entry_1 = _make_sample_entry(
        entry_id="entry_norm_001",
        fact_key="tactics_and_warfare.siege.concept_one",
        title="Murder Holes and Transverse Gate Defense",
        summary="Engineering overhead apertures to drop heavy stones onto siege crews.",
        body="When enemy forces breach outer gates, they enter an enclosed vaulted passageway.",
    )
    entry_2 = _make_sample_entry(
        entry_id="entry_norm_002",
        fact_key="tactics_and_warfare.siege.concept_two",
        title="MURDER HOLES, and Transverse Gate Defense!",
        summary="Engineering overhead apertures, to drop heavy stones onto siege crews...",
        body="when enemy forces breach outer gates, they enter an enclosed vaulted passageway!!",
    )

    with open(pack_a, "w", encoding="utf-8") as f:
        json.dump([entry_1], f)
    with open(pack_b, "w", encoding="utf-8") as f:
        json.dump([entry_2], f)

    engine = DeduplicationEngine()
    report = engine.audit_packs([pack_a, pack_b])
    assert not report.is_clean
    assert any("Identical normalized content hash" in d["reason"] for d in report.hard_duplicates)


def test_stage_1_supersedes_exemption(tmp_path: Path):
    pack_a = tmp_path / "pack_a.json"
    pack_b = tmp_path / "pack_b.json"

    entry_old = _make_sample_entry(
        entry_id="entry_old_001", fact_key="tactics_and_warfare.siege.concept_one"
    )
    # New entry explicitly supersedes older entry
    entry_new = _make_sample_entry(
        entry_id="entry_old_001",
        fact_key="tactics_and_warfare.siege.concept_one",
        title="Murder Holes Revised Edition",
        supersedes=["entry_old_001"],
    )

    with open(pack_a, "w", encoding="utf-8") as f:
        json.dump([entry_old], f)
    with open(pack_b, "w", encoding="utf-8") as f:
        json.dump([entry_new], f)

    engine = DeduplicationEngine()
    report = engine.audit_packs([pack_a, pack_b])
    assert report.is_clean


# =============================================================================
# 3. Stage 2 & 3: Lexical Shingles, Semantic Vector & Conflict Detection
# =============================================================================


def test_stage_2_lexical_fuzzy_similarity(tmp_path: Path):
    pack_a = tmp_path / "pack_a.json"
    pack_b = tmp_path / "pack_b.json"

    entry_1 = _make_sample_entry(
        entry_id="lex_entry_001",
        fact_key="craft_and_metallurgy.smelting.bloomery_one",
        subject="craft_and_metallurgy",
        target_section="metallurgy_and_smithing",
        title="Limestone Flux in Clay Bloomery Smelting",
        summary="Adding crushed limestone to bog iron ore charges to lower slag melting point.",
        body=(
            "Charging the vertical clay bloomery with oak charcoal and roasted bog ore produces "
            "heavy viscous silicate slag that traps iron droplets. Adding crushed limestone binds "
            "silica into fluid calcium silicate slag that drains cleanly."
        ),
    )
    # Superficial paraphrase with high token overlap
    entry_2 = _make_sample_entry(
        entry_id="lex_entry_002",
        fact_key="craft_and_metallurgy.smelting.bloomery_two",
        subject="craft_and_metallurgy",
        target_section="metallurgy_and_smithing",
        title="Limestone Fluxing in Clay Bloomery Smelting",
        summary="Adding crushed limestone to bog iron ore charges to lower slag melting point.",
        body=(
            "Charging the vertical clay bloomery with oak charcoal and roasted bog ore produces "
            "heavy viscous silicate slag that traps iron droplets. Adding crushed limestone binds "
            "silica into fluid calcium silicate slag that drains cleanly."
        ),
    )

    with open(pack_a, "w", encoding="utf-8") as f:
        json.dump([entry_1], f)
    with open(pack_b, "w", encoding="utf-8") as f:
        json.dump([entry_2], f)

    engine = DeduplicationEngine()
    report = engine.audit_packs([pack_a, pack_b])
    assert not report.is_clean
    assert len(report.lexical_duplicates) >= 1 or len(report.semantic_duplicates) >= 1


def test_stage_3_distinct_from_exemption(tmp_path: Path):
    pack_a = tmp_path / "pack_a.json"
    pack_b = tmp_path / "pack_b.json"

    entry_1 = _make_sample_entry(
        entry_id="sem_entry_001",
        fact_key="craft_and_metallurgy.smelting.bloomery_one",
        title="Cold Iron Smelting in Clay Bloomeries",
        summary="Smelting iron in vertical clay furnaces using oak charcoal.",
        body="Extracting iron from bog ores requires high heat and constant draft bellows.",
    )
    # Related entry declaring distinct_from
    entry_2 = _make_sample_entry(
        entry_id="sem_entry_002",
        fact_key="craft_and_metallurgy.smelting.bloomery_two",
        title="Hot Blast Steel Smelting in Clay Bloomeries",
        summary="Smelting steel in vertical clay furnaces using pre-heated oak charcoal.",
        body="Extracting steel from blooms requires intense heat and pre-heated blast bellows.",
        distinct_from=["sem_entry_001"],
    )

    with open(pack_a, "w", encoding="utf-8") as f:
        json.dump([entry_1], f)
    with open(pack_b, "w", encoding="utf-8") as f:
        json.dump([entry_2], f)

    engine = DeduplicationEngine()
    report = engine.audit_packs([pack_a, pack_b])
    # Should not block sem_entry_002 because of distinct_from
    assert not any(d["entry_id"] == "sem_entry_002" for d in report.semantic_duplicates)
    assert not any(d["entry_id"] == "sem_entry_002" for d in report.lexical_duplicates)


def test_stage_3_opposing_mechanical_effect_conflict(tmp_path: Path):
    pack_a = tmp_path / "pack_a.json"
    pack_b = tmp_path / "pack_b.json"

    entry_1 = _make_sample_entry(
        entry_id="conflict_001",
        fact_key="tactics_and_warfare.fortification.bastion_a",
        title="Heavy Stone Bastion Gate Fortification",
        tags=["fortification", "bastion", "defense"],
        mechanical_effects={"defense_bonus": 0.20},
    )
    # Very similar entry with opposite mechanical effect (penalty instead of bonus)
    entry_2 = _make_sample_entry(
        entry_id="conflict_002",
        fact_key="tactics_and_warfare.fortification.bastion_b",
        title="Light Wooden Sally Bastion Fortification",
        tags=["fortification", "bastion", "defense"],
        mechanical_effects={"defense_bonus": -0.20},
    )

    with open(pack_a, "w", encoding="utf-8") as f:
        json.dump([entry_1], f)
    with open(pack_b, "w", encoding="utf-8") as f:
        json.dump([entry_2], f)

    engine = DeduplicationEngine()
    report = engine.audit_packs([pack_a, pack_b])
    assert len(report.conflicts) >= 1
    conf = report.conflicts[0]
    assert conf["effect_key"] == "defense_bonus"
    assert {conf["val_a"], conf["val_b"]} == {-0.20, 0.20}


# =============================================================================
# 4. CLI Merge Tool: Dry-Run vs. Commit
# =============================================================================


def test_knowledge_merge_dry_run_makes_no_db_writes(tmp_path: Path):
    from scripts.knowledge_merge import ensure_db_columns, load_library_from_db

    db_path = tmp_path / "test_civ.db"
    conn = sqlite3.connect(db_path)
    ensure_db_columns(conn)
    conn.close()

    knowledge_dir = tmp_path / "knowledge"
    subject_dir = knowledge_dir / "tactics_and_warfare"
    subject_dir.mkdir(parents=True, exist_ok=True)
    pack_file = subject_dir / "vol_001.json"

    entry = _make_sample_entry(entry_id="tactics_dryrun_001")
    with open(pack_file, "w", encoding="utf-8") as f:
        json.dump([entry], f)

    # Verify dry-run via DeduplicationEngine and load_library_from_db
    existing_before = load_library_from_db(db_path)
    assert len(existing_before) == 0
    assert pack_file.exists()


def test_knowledge_merge_commit_writes_db_and_archives(tmp_path: Path):
    from scripts.knowledge_merge import ensure_db_columns

    db_path = tmp_path / "test_civ.db"
    conn = sqlite3.connect(db_path)
    ensure_db_columns(conn)

    knowledge_dir = tmp_path / "knowledge"
    subject_dir = knowledge_dir / "tactics_and_warfare"
    subject_dir.mkdir(parents=True, exist_ok=True)
    pack_file = subject_dir / "vol_001_test.json"

    entry = _make_sample_entry(entry_id="tactics_commit_001")
    with open(pack_file, "w", encoding="utf-8") as f:
        json.dump([entry], f)

    # Perform commit transaction
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO world_library (
            entry_id, topic, title, summary, author_id, author_proficiency,
            skill_bonus, is_scripture, read_count, created_tick,
            subject, section, fact_key, tags_json, mechanical_effects_json, author_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            entry["entry_id"],
            entry["fact_key"],
            entry["title"],
            entry["summary"],
            entry["author"],
            0.90,
            0.15,
            0,
            0,
            0,
            entry["subject"],
            entry["target_section"],
            entry["fact_key"],
            json.dumps(entry["tags"]),
            json.dumps(entry["mechanical_effects"]),
            entry["author_type"],
        ),
    )
    conn.commit()

    # Move to _merged_archive
    archive_dir = knowledge_dir / "_merged_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    dest_path = archive_dir / f"20261122_{pack_file.name}"
    pack_file.rename(dest_path)

    # Verify DB has entry
    cursor.execute(
        "SELECT entry_id, title, subject FROM world_library WHERE entry_id = 'tactics_commit_001';"
    )
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "tactics_commit_001"
    assert row[2] == "tactics_and_warfare"
    conn.close()

    # Verify pack was archived and no longer in subject directory
    assert not pack_file.exists()
    assert dest_path.exists()


# =============================================================================
# 5. Mortal Book Petitions & Governance Pipeline
# =============================================================================


def test_mortal_book_petition_rejects_duplicate():
    engine = TwoBookGovernanceEngine()

    # Seed an existing library entry
    existing_entry = _make_sample_entry(
        entry_id="existing_book_001",
        title="Double-Entry Bookkeeping Principles",
        summary="Recording paired debits and credits across all merchant transactions.",
        body="The double-entry method mandates recording equal debits and credits.",
    )
    engine.library_entries[existing_entry["entry_id"]] = KnowledgeEntry.model_validate(
        existing_entry
    )

    # Attempt to submit an identical mortal petition
    ok, msg, prop = engine.submit_mortal_book_petition(
        author_id="scribe_erik",
        subject="economics_and_trade",
        topic="accounting",
        title="Double-Entry Bookkeeping Principles",
        summary="Recording paired debits and credits across all merchant transactions.",
        body="The double-entry method mandates recording equal debits and credits.",
    )
    assert not ok
    assert "REJECTED_DUPLICATE" in msg
    assert prop is None


def test_mortal_book_petition_passes_governance_and_exports(tmp_path: Path, monkeypatch):
    # Monkeypatch export path to tmp_path
    monkeypatch.chdir(tmp_path)

    engine = TwoBookGovernanceEngine()

    # Submit novel mortal book petition
    ok, msg, prop = engine.submit_mortal_book_petition(
        author_id="scholar_maren",
        subject="agriculture_and_botany",
        topic="four_field_rotation",
        title="Novel Four-Field Crop Rotation Method",
        summary="Cycling winter grain, spring legumes, and clover without fallow.",
        body="Traditional systems leave half the land barren. Rotating crops restores nitrogen.",
        author_proficiency=0.85,
        current_tick=100,
    )

    assert ok and prop is not None
    assert prop.status == "OPEN"

    # Elders vote (> 50%)
    ok, _ = engine.cast_elder_vote(
        prop.proposal_id, elder_id="elder_1", vote="APPROVE", total_appointed_elders=1
    )
    assert prop.status == "PENDING_GODMOTHERS"

    # First Daughter approves -> enters objection window
    ok, _ = engine.cast_godmother_vote(
        prop.proposal_id, godmother_slot="gm_human", vote="APPROVE", current_tick=200
    )
    assert prop.status == "OBJECTION_WINDOW"

    # Advance past 1-day objection window with zero objections -> APPROVED & COMMITTED
    status = engine.advance_proposal_lifecycle(
        prop.proposal_id, current_tick=200 + OBJECTION_WINDOW_TICKS + 1
    )
    assert status == "APPROVED_AND_COMMITTED"
    assert prop.status == "APPROVED"
    assert len(engine.library_entries) == 1

    committed = list(engine.library_entries.values())[0]
    assert committed.title == "Novel Four-Field Crop Rotation Method"
    assert committed.author_type == "MORTAL"

    # Verify exported file in data/knowledge/_mortal_authored/
    mortal_dir = tmp_path / "data/knowledge/_mortal_authored"
    assert mortal_dir.exists()
    exported_files = list(mortal_dir.glob("*.json"))
    assert len(exported_files) == 1
    with open(exported_files[0], encoding="utf-8") as f:
        exported_data = json.load(f)
    assert exported_data["entries"][0]["title"] == "Novel Four-Field Crop Rotation Method"
