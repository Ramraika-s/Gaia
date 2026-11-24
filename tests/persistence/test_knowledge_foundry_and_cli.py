# tests/persistence/test_knowledge_foundry_and_cli.py
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from scripts.celestial_ingest import run_ingest
from sim_core.knowledge.db_loader import (
    count_pack_entries,
    ensure_world_library_schema,
    load_library_from_db,
)
from sim_core.knowledge.dedupe import DeduplicationEngine
from sim_core.knowledge.schema import KnowledgeEntry, KnowledgePack, validate_anachronisms
from sim_core.persistence.db import init_db


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


def test_schema_valid_pack() -> None:
    entry_dict = _make_sample_entry()
    pack = KnowledgePack.model_validate([entry_dict])
    assert len(pack.entries) == 1
    assert pack.entries[0].entry_id == "tactics_sample_001"
    assert pack.entries[0].subject == "tactics_and_warfare"


def test_schema_rejects_greater_than_30_entries() -> None:
    entries = [
        _make_sample_entry(
            entry_id=f"tactics_entry_{i:03d}", fact_key=f"tactics_and_warfare.siege.k_{i}"
        )
        for i in range(31)
    ]
    with pytest.raises(ValidationError) as exc_info:
        KnowledgePack.model_validate(entries)
    assert "at most 30" in str(exc_info.value) or "30" in str(exc_info.value)


def test_schema_rejects_anachronisms() -> None:
    bad_summary = _make_sample_entry(
        summary="Using electricity to shock advancing infantry at the gate."
    )
    with pytest.raises(ValidationError) as exc:
        KnowledgeEntry.model_validate(bad_summary)
    assert "electricity" in str(exc.value)

    bad_title = _make_sample_entry(title="Deploying Smartphone Telecommunications Across Bastions")
    with pytest.raises(ValidationError) as exc:
        KnowledgeEntry.model_validate(bad_title)
    assert "smartphone" in str(exc.value)

    bad_body = _make_sample_entry(
        body="This defensive doctrine was first codified on the medieval Wikipedia page."
    )
    with pytest.raises(ValidationError) as exc:
        KnowledgeEntry.model_validate(bad_body)
    assert "wikipedia" in str(exc.value)

    bad_tag = _make_sample_entry(tags=["fortification", "nuclear"])
    with pytest.raises(ValidationError) as exc:
        KnowledgeEntry.model_validate(bad_tag)
    assert "nuclear" in str(exc.value)


def test_anachronism_function_helper() -> None:
    assert validate_anachronisms("We harness clean solar electricity.") == "electricity"
    assert validate_anachronisms("A stone masonry arch with lime mortar.") is None


def test_stage_1_exact_and_normalized_duplicates(tmp_path: Path) -> None:
    pack_a_path = tmp_path / "pack_a.json"
    pack_b_path = tmp_path / "pack_b.json"

    entry_1 = _make_sample_entry(
        entry_id="entry_unique_001", fact_key="tactics_and_warfare.siege.concept_a"
    )
    entry_2 = _make_sample_entry(
        entry_id="entry_unique_001", fact_key="tactics_and_warfare.siege.concept_b"
    )

    with open(pack_a_path, "w", encoding="utf-8") as f:
        json.dump([entry_1], f)
    with open(pack_b_path, "w", encoding="utf-8") as f:
        json.dump([entry_2], f)

    engine = DeduplicationEngine()
    report = engine.audit_packs([pack_a_path, pack_b_path])
    assert not report.is_clean
    assert len(report.hard_duplicates) >= 1
    assert any("entry_id collision" in d["reason"] for d in report.hard_duplicates)


def test_stage_1_normalized_text_hash_collision(tmp_path: Path) -> None:
    pack_a = tmp_path / "pack_a.json"
    pack_b = tmp_path / "pack_b.json"

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


def test_stage_1_supersedes_exemption(tmp_path: Path) -> None:
    pack_a = tmp_path / "pack_a.json"
    pack_b = tmp_path / "pack_b.json"

    entry_old = _make_sample_entry(
        entry_id="entry_old_001", fact_key="tactics_and_warfare.siege.concept_one"
    )
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


def test_stage_2_lexical_fuzzy_similarity(tmp_path: Path) -> None:
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


def test_stage_3_distinct_from_exemption(tmp_path: Path) -> None:
    pack_a = tmp_path / "pack_a.json"
    pack_b = tmp_path / "pack_b.json"

    entry_1 = _make_sample_entry(
        entry_id="sem_entry_001",
        fact_key="craft_and_metallurgy.smelting.bloomery_one",
        title="Cold Iron Smelting in Clay Bloomeries",
        summary="Smelting iron in vertical clay furnaces using oak charcoal.",
        body="Extracting iron from bog ores requires high heat and constant draft bellows.",
    )
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
    assert not any(d["entry_id"] == "sem_entry_002" for d in report.semantic_duplicates)
    assert not any(d["entry_id"] == "sem_entry_002" for d in report.lexical_duplicates)


def test_stage_3_opposing_mechanical_effect_conflict(tmp_path: Path) -> None:
    pack_a = tmp_path / "pack_a.json"
    pack_b = tmp_path / "pack_b.json"

    entry_1 = _make_sample_entry(
        entry_id="conflict_001",
        fact_key="tactics_and_warfare.fortification.bastion_a",
        title="Heavy Stone Bastion Gate Fortification",
        tags=["fortification", "bastion", "defense"],
        mechanical_effects={"defense_bonus": 0.20},
    )
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


def test_knowledge_merge_dry_run_makes_no_db_writes(tmp_path: Path) -> None:
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

    existing_before = load_library_from_db(db_path)
    assert len(existing_before) == 0
    assert pack_file.exists()


def test_knowledge_merge_commit_writes_db_and_archives(tmp_path: Path) -> None:
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

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO world_library
        (entry_id, topic, title, summary, author_id, author_proficiency,
         skill_bonus, is_scripture, read_count, created_tick, body, subject,
         section, mechanical_effects_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?, ?, ?, ?)
        """,
        (
            entry["entry_id"],
            entry["target_section"],
            entry["title"],
            entry["summary"],
            entry["author"],
            1.0,
            0.15,
            entry["body"],
            entry["subject"],
            entry["target_section"],
            json.dumps(entry["mechanical_effects"]),
        ),
    )
    conn.commit()

    rows = conn.execute("SELECT count(*) FROM world_library").fetchone()[0]
    assert rows == 1
    conn.close()


def test_celestial_lore_harvester_offline_and_anachronism_rejection() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "celestial_metallurgy.md"
        output_file = Path(tmpdir) / "pack_craft.json"

        input_file.write_text(
            """# The Sacred Crucible of Aethelgard

Ancient smiths learned that tempering sky-iron under moonlight grants weapons sharpness.
By folding the ore seven times in dragon flame, the steel resists corrosion and absorbs shock.
The craftsmen spoke through an internet of whispers and used a computer of stars for ratios.

## Techniques of the Deep Forge

Deep in the obsidian caves, dwarven masters blend volcanic sulfur with mithril ingots.
This union produces armor impenetrable by mundane arrows, radiating a faint azure glow.
""",
            encoding="utf-8",
        )

        pack = run_ingest(
            input_path=input_file,
            subject="craft_and_metallurgy",
            output_path=output_file,
            use_llm=False,
            max_entries=5,
            era_tier=2,
            author="Master Vane",
        )

        assert len(pack.entries) >= 1
        assert pack.entries[0].subject == "craft_and_metallurgy"
        assert output_file.exists()

        for entry in pack.entries:
            assert "internet" not in entry.body.lower()
            assert "computer" not in entry.body.lower()
            assert len(entry.entry_id) >= 4
            assert len(entry.fact_key.split(".")) == 3
            assert entry.era_tier == 2
            assert entry.author == "Master Vane"


def test_knowledge_foundry_cli_end_to_end(tmp_path: Path) -> None:
    db_path = tmp_path / "civilization.db"
    init_db(db_path)
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        ensure_world_library_schema(conn)
        conn.execute(
            """
            INSERT INTO world_library
            (entry_id, topic, title, summary, author_id, author_proficiency,
             skill_bonus, created_tick, body, subject, section)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "tactics_001",
                "siege",
                "Defensive Shield Walls",
                "Overlapping shields to deflect volleys.",
                "Leon",
                1.0,
                0.08,
                0,
                "Formation must interlock rims firmly and advance in tight coordination.",
                "tactics_and_warfare",
                "siege",
            ),
        )
        conn.commit()

    lib = load_library_from_db(db_path)
    lib_map = {e["entry_id"]: e for e in lib}
    assert "tactics_001" in lib_map
    assert lib_map["tactics_001"]["body"] == (
        "Formation must interlock rims firmly and advance in tight coordination."
    )

    pack_data = {
        "pack_id": "test_pack_wave5",
        "subject": "tactics_and_warfare",
        "target_section": "infantry",
        "entries": [
            {
                "entry_id": "tactics_dup",
                "subject": "tactics_and_warfare",
                "target_section": "siege",
                "fact_key": "tactics.siege.shield_wall",
                "title": "Defensive Shield Walls",
                "summary": "Overlapping shields to deflect volleys.",
                "body": ("Formation must interlock rims firmly and advance in tight coordination."),
                "author": "Copycat",
                "era_tier": 1,
            },
            {
                "entry_id": "tactics_novel_001",
                "subject": "tactics_and_warfare",
                "target_section": "infantry",
                "fact_key": "tactics.infantry.pike_phalanx",
                "title": "Extended Pike Phalanx Formation",
                "summary": "Five-meter ash pikes deployed in dense multi-rank formation.",
                "body": (
                    "The front five ranks project pikes horizontally against cavalry charges, "
                    "creating an impenetrable wall of spear points."
                ),
                "author": "General Philip",
                "era_tier": 1,
            },
        ],
    }

    pack_path = knowledge_dir / "pack_tactics.json"
    with open(pack_path, "w", encoding="utf-8") as f:
        json.dump(pack_data, f)

    assert count_pack_entries(pack_path) == 2

    import scripts.celestial_ingest as celestial_ingest
    import scripts.knowledge_merge as knowledge_merge
    import scripts.knowledge_review as knowledge_review

    passed_dup, reason_dup, _ = celestial_ingest.audit_single_entry(pack_data["entries"][0], lib)
    assert not passed_dup
    assert "DUPLICATE" in reason_dup

    passed_novel, _, _ = celestial_ingest.audit_single_entry(pack_data["entries"][1], lib)
    assert passed_novel

    novel_pack_data = dict(pack_data)
    novel_pack_data["entries"] = [pack_data["entries"][1]]
    with open(pack_path, "w", encoding="utf-8") as f:
        json.dump(novel_pack_data, f)

    rev_code = knowledge_review.main(
        [
            "--knowledge-dir",
            str(knowledge_dir),
            "--pack",
            str(pack_path),
            "--db-path",
            str(db_path),
        ]
    )
    assert rev_code == 0

    merge_code = knowledge_merge.main(
        [
            "--knowledge-dir",
            str(knowledge_dir),
            "--pack",
            str(pack_path),
            "--db-path",
            str(db_path),
            "--commit",
        ]
    )
    assert merge_code == 0

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT title, body, author_id FROM world_library WHERE entry_id = 'tactics_novel_001'"
        ).fetchone()
        assert row is not None
        assert row[0] == "Extended Pike Phalanx Formation"
        expected_body = (
            "The front five ranks project pikes horizontally against cavalry charges, "
            "creating an impenetrable wall of spear points."
        )
        assert row[1] == expected_body
        assert row[2] == "General Philip"


def test_knowledge_tools_edge_cases(tmp_path: Path) -> None:
    import scripts.celestial_ingest as celestial_ingest
    import scripts.knowledge_merge as knowledge_merge
    import scripts.knowledge_review as knowledge_review

    bad_pack = tmp_path / "bad_pack.json"
    with open(bad_pack, "w", encoding="utf-8") as f:
        json.dump({"meta": "info", "version": 1}, f)
    assert count_pack_entries(bad_pack) == 0

    k_dir = tmp_path / "k_packs"
    k_dir.mkdir()
    sib1 = k_dir / "pack_a.json"
    sib2 = k_dir / "pack_b.json"

    entry_shared = {
        "entry_id": "mining_001",
        "subject": "craft_and_metallurgy",
        "target_section": "metallurgy",
        "fact_key": "craft.mining.iron_veins",
        "title": "Subterranean Iron Vein Identification",
        "summary": "Identifying hematite and magnetite formations in limestone strata.",
        "body": "Look for rust staining and magnetic deflection in karst formations.",
        "author": "Prospector",
        "era_tier": 1,
    }
    with open(sib1, "w", encoding="utf-8") as f:
        json.dump(
            {"pack_id": "pack_a", "subject": "craft_and_metallurgy", "entries": [entry_shared]}, f
        )

    with open(sib2, "w", encoding="utf-8") as f:
        json.dump(
            {"pack_id": "pack_b", "subject": "craft_and_metallurgy", "entries": [entry_shared]}, f
        )

    db_path = tmp_path / "test_kb.db"
    init_db(db_path)

    rev_code = knowledge_review.main(
        [
            "--knowledge-dir",
            str(k_dir),
            "--pack",
            str(sib2),
            "--db-path",
            str(db_path),
        ]
    )
    assert rev_code == 1

    custom_archive = tmp_path / "my_custom_archive"
    entry_novel = dict(entry_shared)
    entry_novel["entry_id"] = "mining_novel_999"
    entry_novel["fact_key"] = "craft.mining.deep_silver"
    entry_novel["title"] = "Deep Silver Extraction Methods"
    entry_novel["body"] = (
        "Smelting galena ores using high-temperature bone ash "
        "cupellation to isolate pure silver bullion."
    )

    sib1.unlink()
    with open(sib2, "w", encoding="utf-8") as f:
        json.dump(
            {"pack_id": "pack_b", "subject": "craft_and_metallurgy", "entries": [entry_novel]}, f
        )

    merge_code = knowledge_merge.main(
        [
            "--knowledge-dir",
            str(k_dir),
            "--pack",
            str(sib2),
            "--db-path",
            str(db_path),
            "--archive-dir",
            str(custom_archive),
            "--commit",
        ]
    )
    assert merge_code == 0
    assert custom_archive.exists()
    archived_files = list(custom_archive.glob("*.json"))
    assert len(archived_files) == 1

    lore_doc = tmp_path / "lore.txt"
    lore_doc.write_text(
        "Deep Silver Extraction Methods. Smelting galena ores using bone ash cupellation."
    )
    out_pack = tmp_path / "ingest_out.json"

    with pytest.raises(ValueError, match="All candidate entries were rejected as duplicates"):
        celestial_ingest.run_ingest(
            input_path=lore_doc,
            subject="craft_and_metallurgy",
            output_path=out_pack,
            use_llm=False,
            db_path=db_path,
            knowledge_dir=k_dir,
        )
