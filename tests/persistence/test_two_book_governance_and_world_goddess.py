# tests/persistence/test_two_book_governance_and_world_goddess.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sim_core.bridge.godot_ws_bridge import resolve_library_entry_id
from sim_core.divine.hierarchy import DivineHierarchyManager
from sim_core.divine.sister_council import SisterCouncilEngine
from sim_core.engine import SimulationEngine
from sim_core.knowledge.schema import KnowledgeEntry
from sim_core.persistence.world_goddess import CommitProposal, WorldGoddessCritic
from sim_core.schemas import LibraryProposalRecord, WorldLibraryEntry
from sim_core.society.library import (
    EXPIRY_TICKS,
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


def test_world_library_mortal_proposal_lifecycle_and_objection_window() -> None:
    engine = TwoBookGovernanceEngine()

    ok, _, prop = engine.draft_mortal_proposal(
        author_id="scholar_erik",
        topic="Metalsmithing",
        title="Dwarven Alloys",
        summary="Forging methods for high-durability plows.",
        author_proficiency=0.85,
        current_tick=100,
        action="CREATE",
    )
    assert ok and prop is not None
    assert prop.status == "OPEN"

    # Elders vote (> 50%)
    ok, _ = engine.cast_elder_vote(
        prop.proposal_id, elder_id="elder_1", vote="APPROVE", total_appointed_elders=3
    )
    assert ok and prop.status == "OPEN"

    ok, _ = engine.cast_elder_vote(
        prop.proposal_id, elder_id="elder_2", vote="APPROVE", total_appointed_elders=3
    )
    assert ok and prop.status == "PENDING_GODMOTHERS"

    # First Daughter approves -> starts 1-day objection window
    ok, _ = engine.cast_godmother_vote(
        prop.proposal_id, godmother_slot="gm_human", vote="APPROVE", current_tick=200
    )
    assert ok and prop.status == "OBJECTION_WINDOW"
    assert prop.first_approval_tick == 200

    # 1 objection (gm_elf)
    engine.cast_godmother_vote(
        prop.proposal_id, godmother_slot="gm_elf", vote="OBJECT", current_tick=300
    )
    assert prop.status == "OBJECTION_WINDOW"

    status = engine.advance_proposal_lifecycle(
        prop.proposal_id, current_tick=200 + OBJECTION_WINDOW_TICKS + 1
    )
    assert status == "APPROVED_AND_COMMITTED"
    assert prop.status == "APPROVED"
    assert len(engine.library_entries) == 1
    committed_entry = list(engine.library_entries.values())[0]
    assert committed_entry.title == "Dwarven Alloys"


def test_world_library_daughter_objection_block_and_appeal() -> None:
    engine = TwoBookGovernanceEngine()

    _, _, prop = engine.draft_mortal_proposal(
        author_id="heretic_bob",
        topic="DarkArts",
        title="Necromancy Basics",
        summary="Raising fallen units.",
        author_proficiency=0.9,
        current_tick=10,
        action="CREATE",
    )
    assert prop is not None

    engine.cast_elder_vote(
        prop.proposal_id, elder_id="elder_1", vote="APPROVE", total_appointed_elders=1
    )
    assert prop.status == "PENDING_GODMOTHERS"

    engine.cast_godmother_vote(prop.proposal_id, "gm_human", "APPROVE", current_tick=20)
    engine.cast_godmother_vote(prop.proposal_id, "gm_elf", "OBJECT", current_tick=25)
    engine.cast_godmother_vote(prop.proposal_id, "gm_dragon", "OBJECT", current_tick=30)
    ok, msg = engine.cast_godmother_vote(
        prop.proposal_id, "gm_beasthuman", "OBJECT", current_tick=35
    )

    assert ok and msg == "BLOCKED_BY_DAUGHTERS"
    assert prop.status == "BLOCKED_BY_DAUGHTERS"

    status = engine.advance_proposal_lifecycle(
        prop.proposal_id, current_tick=20 + OBJECTION_WINDOW_TICKS + 100
    )
    assert status == "BLOCKED_BY_DAUGHTERS"

    ok, _ = engine.appeal_blocked_proposal(prop.proposal_id, "WORLD_GODDESS")
    assert ok and prop.appeal_target == "WORLD_GODDESS"

    ok, _ = engine.resolve_appeal_world_goddess(prop.proposal_id, approved=True, current_tick=60)
    assert ok and prop.status == "APPROVED"
    assert len(engine.library_entries) == 1


def test_world_library_expiry_after_30_days() -> None:
    engine = TwoBookGovernanceEngine()

    _, _, prop = engine.draft_mortal_proposal(
        author_id="forgotten_author",
        topic="Trivia",
        title="Unread Lore",
        summary="Obscure notes.",
        author_proficiency=0.75,
        current_tick=0,
        action="CREATE",
    )
    assert prop is not None
    engine.cast_elder_vote(
        prop.proposal_id, elder_id="elder_1", vote="APPROVE", total_appointed_elders=1
    )
    assert prop.status == "PENDING_GODMOTHERS"

    status = engine.advance_proposal_lifecycle(prop.proposal_id, current_tick=EXPIRY_TICKS - 1)
    assert status == "PENDING_GODMOTHERS"

    status = engine.advance_proposal_lifecycle(prop.proposal_id, current_tick=EXPIRY_TICKS + 1)
    assert status == "EXPIRED"
    assert prop.status == "EXPIRED"


def test_world_library_divine_direct_edits() -> None:
    """
    Verifies divine writing authority:
    - God direct edit succeeds.
    - Goddess + >= 1 Daughter succeeds.
    - 3/5 Daughters alone succeeds.
    - 2/5 Daughters alone fails.
    """
    engine = TwoBookGovernanceEngine()

    # 1. God direct edit
    e_god = WorldLibraryEntry(
        entry_id="entry_god_1",
        topic="Cosmology",
        title="Origin of the World",
        summary="Decreed by God.",
        author_id="GOD",
        author_proficiency=1.0,
        is_scripture=True,
        created_tick=1,
    )
    ok, msg = engine.write_library_direct_god(e_god)
    assert ok and "entry_god_1" in engine.library_entries

    # 2. Goddess + 1 Daughter succeeds
    e_goddess = WorldLibraryEntry(
        entry_id="entry_goddess_1",
        topic="Morals",
        title="Virtue of Harmony",
        summary="Wisdom of the Mother.",
        author_id="world_goddess",
        author_proficiency=1.0,
        created_tick=2,
    )
    ok, msg = engine.write_library_goddess_with_daughters(
        e_goddess, daughter_approvals=["gm_human"]
    )
    assert ok and "entry_goddess_1" in engine.library_entries

    # 3. 2/5 Daughters alone FAILS (< 3 required)
    e_daughters = WorldLibraryEntry(
        entry_id="entry_daughters_1",
        topic="Biology",
        title="Beast & Dragon Physiology",
        summary="Sisters joint study.",
        author_id="gm_dragon",
        author_proficiency=0.9,
        created_tick=3,
    )
    ok, msg = engine.write_library_daughters_alone(
        e_daughters, daughter_approvals=["gm_dragon", "gm_beasthuman"]
    )
    assert not ok and "REJECTED" in msg

    # 4. 3/5 Daughters alone SUCCEEDS (>= 3 of 5)
    ok, msg = engine.write_library_daughters_alone(
        e_daughters, daughter_approvals=["gm_dragon", "gm_beasthuman", "gm_demon"]
    )
    assert ok and "entry_daughters_1" in engine.library_entries


def test_divine_codex_option_b_split_write_authority() -> None:
    engine = TwoBookGovernanceEngine()
    critic = WorldGoddessCritic()

    # 1. World Goddess + 3/5 Daughters writes non-mechanical text decree
    ok, _, entry = engine.write_codex_text_decree_goddess_and_daughters(
        title="Sanctity of Sacred Groves",
        text="No timber shall be felled within 3 chunks of high altars.",
        daughter_approvals=["gm_elf", "gm_human", "gm_beasthuman"],
        current_tick=100,
    )
    assert ok and entry is not None
    assert entry.category == "DECREE"

    prop_decree = CommitProposal(
        proposal_id="prop_dec_1",
        kind="DIVINE_CODEX_DECREE",
        actor_id="world_goddess",
        tick=100,
        payload={
            "author_slot": "world_goddess",
            "supporting_daughter_slots": ["gm_elf", "gm_human", "gm_beasthuman"],
            "category": "DECREE",
        },
    )
    assert critic.evaluate(prop_decree).status == "SUCCESS"

    # 2. Direct parameter override attempt by Goddess + Daughters is BLOCKED
    prop_override_illegal = CommitProposal(
        proposal_id="prop_ovr_bad",
        kind="DIVINE_CODEX_DECREE",
        actor_id="world_goddess",
        tick=101,
        payload={
            "author_slot": "world_goddess",
            "supporting_daughter_slots": ["gm_elf", "gm_human", "gm_beasthuman", "gm_dragon"],
            "category": "PARAMETER_OVERRIDE",
            "parameter_key": "DIVINE_TRUCE_DURATION_TICKS",
            "parameter_value_json": json.dumps(15000),
        },
    )
    verdict_bad = critic.evaluate(prop_override_illegal)
    assert verdict_bad.status == "FAILURE"
    assert "Option B" in verdict_bad.reason

    # 3. Goddess submits parameter proposal to God
    ok, _, codex_prop = engine.submit_parameter_override_proposal(
        title="Extend Divine Truce",
        text="Increase truce duration to 15,000 ticks during Holy festivals.",
        parameter_key="DIVINE_TRUCE_DURATION_TICKS",
        parameter_value=15000,
        proposer_slot="world_goddess",
        co_sponsors=[],
        current_tick=102,
    )
    assert ok and codex_prop is not None
    assert codex_prop.status == "PENDING_GOD"

    ok, _, approved_entry = engine.approve_codex_proposal_by_god(
        codex_prop.proposal_id, current_tick=105
    )
    assert ok and approved_entry is not None
    assert engine.live_engine_overrides["DIVINE_TRUCE_DURATION_TICKS"] == 15000


def test_conception_rbac_validation() -> None:
    critic = WorldGoddessCritic()

    # Reject same-gender mating
    prop_boy_boy = CommitProposal(
        proposal_id="prop_01",
        tick=100,
        kind="CONCEPTION",
        payload={
            "parent1_gender": "BOY",
            "parent2_gender": "BOY",
            "parent1_race": "HUMAN",
            "parent2_race": "HUMAN",
        },
    )
    v1 = critic.evaluate(prop_boy_boy)
    assert v1.status == "FAILURE"
    assert "one BOY and one GIRL" in v1.reason

    # Reject TRUE_DRAGON mating
    prop_true_dragon = CommitProposal(
        proposal_id="prop_03",
        tick=102,
        kind="CONCEPTION",
        payload={
            "parent1_gender": "BOY",
            "parent2_gender": "GIRL",
            "parent1_race": "DRAGON",
            "parent1_dragon_form": "TRUE_DRAGON",
            "parent2_race": "HUMAN",
        },
    )
    v3 = critic.evaluate(prop_true_dragon)
    assert v3.status == "FAILURE"
    assert "HUMANOID_DRAGON form" in v3.reason

    # Approve valid opposite-gender HUMANOID_DRAGON mating
    prop_valid = CommitProposal(
        proposal_id="prop_04",
        tick=103,
        kind="CONCEPTION",
        payload={
            "parent1_gender": "BOY",
            "parent2_gender": "GIRL",
            "parent1_race": "DRAGON",
            "parent1_dragon_form": "HUMANOID_DRAGON",
            "parent2_race": "HUMAN",
            "conception_roll": 0.40,
        },
    )
    assert critic.evaluate(prop_valid).status == "SUCCESS"


def test_library_and_elder_governance() -> None:
    critic = WorldGoddessCritic()

    # Mortal edit without Elder quorum (>50%) rejected
    prop_mortal = CommitProposal(
        proposal_id="lib_01",
        tick=200,
        kind="LIBRARY_ENTRY",
        payload={
            "author_id": "mortal_scholar",
            "topic": "agriculture",
            "elder_approvals_count": 2,
            "total_appointed_elders": 4,
            "author_proficiency": 0.85,
        },
    )
    v1 = critic.evaluate(prop_mortal)
    assert v1.status == "FAILURE"
    assert ">50% Council of Elders" in v1.reason

    # Mortal edit with strict majority (>50%) approved
    prop_approved = CommitProposal(
        proposal_id="lib_02",
        tick=201,
        kind="LIBRARY_ENTRY",
        payload={
            "author_id": "mortal_scholar",
            "topic": "agriculture",
            "elder_approvals_count": 3,
            "total_appointed_elders": 4,
            "author_proficiency": 0.85,
        },
    )
    assert critic.evaluate(prop_approved).status == "SUCCESS"

    # Nation appointing a 3rd Library Elder rejected
    prop_3rd_elder = CommitProposal(
        proposal_id="settle_01",
        tick=202,
        kind="SETTLEMENT_UPDATE",
        payload={
            "sub_action": "APPOINT_LIBRARY_ELDER",
            "nation_id": "nation_solis",
            "current_nation_elders_count": 2,
            "target_elder_id": "elder_candidate",
        },
    )
    v3 = critic.evaluate(prop_3rd_elder)
    assert v3.status == "FAILURE"
    assert "maximum 2 Library Elders" in v3.reason


def test_judiciary_self_defense_and_war_protection() -> None:
    critic = WorldGoddessCritic()

    # Attempt to convict verified SELF_DEFENSE with BANISHMENT -> REJECTED
    prop_convict_defense = CommitProposal(
        proposal_id="case_01",
        tick=400,
        kind="JUDICIARY_RULING",
        payload={
            "case_id": "c_001",
            "combat_context": "SELF_DEFENSE",
            "ruling": "BANISHMENT",
        },
    )
    v1 = critic.evaluate(prop_convict_defense)
    assert v1.status == "FAILURE"
    assert "unlawful conviction" in v1.reason

    # Attempt to fine verified ACTIVE_WAR combatant -> REJECTED
    prop_convict_war = CommitProposal(
        proposal_id="case_02",
        tick=401,
        kind="JUDICIARY_RULING",
        payload={
            "case_id": "c_002",
            "combat_context": "ACTIVE_WAR",
            "ruling": "FINE",
        },
    )
    v2 = critic.evaluate(prop_convict_war)
    assert v2.status == "FAILURE"
    assert "unlawful conviction" in v2.reason

    # Acquittal of verified SELF_DEFENSE -> APPROVED
    prop_acquit = CommitProposal(
        proposal_id="case_03",
        tick=402,
        kind="JUDICIARY_RULING",
        payload={
            "case_id": "c_003",
            "combat_context": "SELF_DEFENSE",
            "ruling": "ACQUITTED",
        },
    )
    assert critic.evaluate(prop_acquit).status == "SUCCESS"


def test_five_daughter_voting_math_and_demon_rbac() -> None:
    critic = WorldGoddessCritic()

    # Library Daughters-alone: 3/5 succeeds, 2/5 fails
    prop_lib_3of5 = CommitProposal(
        proposal_id="prop_lib_3",
        tick=100,
        actor_id="gm_demon",
        kind="LIBRARY_ENTRY",
        payload={"author_type": "DAUGHTERS", "daughter_approvals_count": 3},
    )
    assert critic.evaluate(prop_lib_3of5).status == "SUCCESS"

    prop_lib_2of5 = CommitProposal(
        proposal_id="prop_lib_2",
        tick=101,
        actor_id="gm_demon",
        kind="LIBRARY_ENTRY",
        payload={"author_type": "DAUGHTERS", "daughter_approvals_count": 2},
    )
    v_lib_2 = critic.evaluate(prop_lib_2of5)
    assert v_lib_2.status == "FAILURE"
    assert "at least 3 of 5" in v_lib_2.reason

    # Mortal proposal blocked by >= 3/5 God-Mother objections
    prop_mortal_blocked = CommitProposal(
        proposal_id="prop_mortal_blk",
        tick=102,
        kind="LIBRARY_ENTRY",
        payload={
            "author_id": "scholar_1",
            "elder_approvals_count": 3,
            "total_appointed_elders": 4,
            "godmother_approvals_count": 1,
            "godmother_objections_count": 3,
            "author_proficiency": 0.85,
        },
    )
    assert critic.evaluate(prop_mortal_blocked).status == "FAILURE"


def test_non_aggression_covenant_and_mediation() -> None:
    hierarchy = DivineHierarchyManager()
    council = SisterCouncilEngine(hierarchy)

    human_mother = hierarchy.get_deity("gm_human")
    assert human_mother.covenant_rebukes == 0

    success, reason = hierarchy.execute_intervention(
        slot="gm_human",
        action="SOOTHE_OR_HEAL",
        current_tick=100,
        target_civilians=True,
    )
    assert success is False
    assert "NON_AGGRESSION_COVENANT_BREACH" in reason
    assert human_mother.covenant_rebukes == 1

    mediation_msg = council.handle_covenant_breach(
        aggressor_slot="gm_human",
        victim_slot="gm_elf",
        day=1,
        tick=100,
    )
    assert mediation_msg.topic == "COVENANT_BREACH"
    assert mediation_msg.resolution is not None
    assert "COVENANT_REBUKE_ISSUED" in mediation_msg.resolution
    assert human_mother.intervention_cooldown_until_tick == 100 + 10800


def test_divine_truce_blocks_wartime_ward_defenders() -> None:
    hierarchy = DivineHierarchyManager()
    council = SisterCouncilEngine(hierarchy)

    accepted, msg = council.propose_truce(
        sender_slot="gm_human",
        target_slot="gm_dragon",
        day=2,
        tick=200,
    )
    assert accepted is True
    assert msg.resolution is not None
    assert "DIVINE_TRUCE_ESTABLISHED" in msg.resolution

    human_mother = hierarchy.get_deity("gm_human")
    dragon_mother = hierarchy.get_deity("gm_dragon")
    assert "gm_dragon" in human_mother.active_truce_with
    assert "gm_human" in dragon_mother.active_truce_with

    success, reason = hierarchy.execute_intervention(
        slot="gm_human",
        action="WARD_DEFENDERS",
        current_tick=300,
        target_slot="gm_dragon",
    )
    assert success is False
    assert "DIVINE_TRUCE_ACTIVE" in reason


def test_two_book_governance_duplicate_vote_exploit_blocked(engine: SimulationEngine) -> None:
    gov = engine.governance_engine

    ok_exploit, reason_exploit, _ = gov.write_codex_text_decree_goddess_and_daughters(
        title="Corrupted Decree",
        text="I declare unlimited wine.",
        daughter_approvals=["gm_human", "gm_human", "gm_human"],
        current_tick=1,
    )
    assert ok_exploit is False
    assert "got 1" in reason_exploit or ">= 3/5 Daughters" in reason_exploit

    ok_valid, _, entry = gov.write_codex_text_decree_goddess_and_daughters(
        title="Sanctioned Decree",
        text="Universal festival day.",
        daughter_approvals=["gm_human", "gm_elf", "gm_dragon"],
        current_tick=1,
    )
    assert ok_valid is True
    assert entry is not None


def test_pure_end_of_day_mortal_book_export_and_crime_pruning(
    engine: SimulationEngine,
) -> None:
    mortal_export_dir = Path("data/knowledge/_mortal_authored")
    if mortal_export_dir.exists():
        for f in mortal_export_dir.glob("*.json"):
            f.unlink()

    prop = LibraryProposalRecord(
        proposal_id="prop_mortal_1",
        action="CREATE",
        author_id="mortal_farmer_1",
        topic="agriculture",
        title="Mortal Agriculture",
        summary="Crop rotation.",
        author_proficiency=0.8,
        status="APPROVED",
        created_tick=100,
    )
    engine.governance_engine._commit_entry_from_proposal(prop, current_tick=100)

    written_midday = list(mortal_export_dir.glob("*.json")) if mortal_export_dir.exists() else []
    assert len(written_midday) == 0
    assert len(engine.governance_engine.pending_mortal_exports) == 1

    engine.commit_end_of_day()
    written_eod = list(mortal_export_dir.glob("*.json"))
    assert len(written_eod) == 1
    assert len(engine.governance_engine.pending_mortal_exports) == 0

    for f in written_eod:
        f.unlink()

    engine.speech_acts.reported_crimes.add(("speaker_old", "theft", 10))
    engine.speech_acts.reported_crimes.add(("speaker_recent", "theft", 55))
    engine.speech_acts.step(current_tick=3300, agents=[])
    assert ("speaker_old", "theft", 10) not in engine.speech_acts.reported_crimes
    assert ("speaker_recent", "theft", 55) in engine.speech_acts.reported_crimes


def test_mortal_book_petition_rejects_duplicate() -> None:
    engine = TwoBookGovernanceEngine()

    existing_entry = _make_sample_entry(
        entry_id="existing_book_001",
        title="Double-Entry Bookkeeping Principles",
        summary="Recording paired debits and credits across all merchant transactions.",
        body="The double-entry method mandates recording equal debits and credits.",
    )
    engine.library_entries[existing_entry["entry_id"]] = KnowledgeEntry.model_validate(
        existing_entry
    )

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


def test_mortal_book_petition_passes_governance_and_exports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    engine = TwoBookGovernanceEngine()

    ok, _, prop = engine.submit_mortal_book_petition(
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

    engine.cast_elder_vote(
        prop.proposal_id, elder_id="elder_1", vote="APPROVE", total_appointed_elders=1
    )
    assert prop.status == "PENDING_GODMOTHERS"

    engine.cast_godmother_vote(
        prop.proposal_id, godmother_slot="gm_human", vote="APPROVE", current_tick=200
    )
    assert prop.status == "OBJECTION_WINDOW"

    status = engine.advance_proposal_lifecycle(
        prop.proposal_id, current_tick=200 + OBJECTION_WINDOW_TICKS + 1
    )
    assert status == "APPROVED_AND_COMMITTED"
    assert prop.status == "APPROVED"
    assert len(engine.library_entries) == 1


def test_resolve_library_entry_id_multi_volume() -> None:
    entries: dict[str, Any] = {}

    id1 = resolve_library_entry_id("PHILOSOPHY", "Ethics", entries)
    assert id1 == "lib_PHILOSOPHY"
    entries[id1] = WorldLibraryEntry(
        entry_id=id1,
        topic="PHILOSOPHY",
        title="Ethics",
        summary="Virtue ethics.",
        author_id="GOD",
        created_tick=0,
    )

    id1_again = resolve_library_entry_id("PHILOSOPHY", "Ethics", entries)
    assert id1_again == "lib_PHILOSOPHY"

    id2 = resolve_library_entry_id("PHILOSOPHY", "Metaphysics", entries)
    assert id2.startswith("lib_philosophy_metaphysics_")
    assert id2 != id1
    entries[id2] = WorldLibraryEntry(
        entry_id=id2,
        topic="PHILOSOPHY",
        title="Metaphysics",
        summary="Forms and substance.",
        author_id="GOD",
        created_tick=0,
    )

    id2_again = resolve_library_entry_id("PHILOSOPHY", "Metaphysics", entries)
    assert id2_again == id2

    id_explicit = resolve_library_entry_id(
        "PHILOSOPHY", "Aesthetics", entries, explicit_entry_id="custom_entry_99"
    )
    assert id_explicit == "custom_entry_99"


def test_resolve_library_entry_id_preserves_id_when_first_volume_deleted() -> None:
    entries: dict[str, Any] = {}
    id1 = resolve_library_entry_id("PHILOSOPHY", "Ethics", entries)
    entries[id1] = WorldLibraryEntry(
        entry_id=id1,
        topic="PHILOSOPHY",
        title="Ethics",
        summary="Virtue ethics.",
        author_id="GOD",
        created_tick=0,
    )

    id2 = resolve_library_entry_id("PHILOSOPHY", "Metaphysics", entries)
    entries[id2] = WorldLibraryEntry(
        entry_id=id2,
        topic="PHILOSOPHY",
        title="Metaphysics",
        summary="Forms and being.",
        author_id="GOD",
        created_tick=0,
    )

    del entries[id1]
    resolved_id2 = resolve_library_entry_id("PHILOSOPHY", "Metaphysics", entries)
    assert resolved_id2 == id2


def test_resolve_library_entry_id_special_chars() -> None:
    entries: dict[str, Any] = {}
    eid = resolve_library_entry_id("DARK MAGIC / CURSES", "Vol 1", entries)
    assert eid == "lib_DARK_MAGIC_CURSES"
