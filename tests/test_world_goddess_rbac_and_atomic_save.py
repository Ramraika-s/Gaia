"""
tests/test_world_goddess_rbac_and_atomic_save.py
Phase 1 Acceptance Tests:
- WorldGoddessCritic RBAC & Validation Matrix:
  - Rejects same-gender mating (BOY+BOY, GIRL+GIRL)
  - Rejects TRUE_DRAGON cross-species mating
  - Blocks mortal world_library edits without strict >50% Appointed Elder Council consensus
  - Rejects a Nation's 3rd Library Elder appointment
  - Allows God bypass (bypass_god_check=True)
  - Rejects CREDIT_TRANSFER when sender.credits < amount (double-entry closed-loop)
  - Rejects JUDICIARY_RULING attempting to convict verified SELF_DEFENSE or ACTIVE_WAR
- Persistence & Atomic SQLite Commits:
  - Mid-commit SQLite failure triggers full ROLLBACK (zero partial rows written)
  - DuckDB read-only attach queries civ.fatalities and civ.agents without locking SQLite
"""

import sqlite3
from pathlib import Path

import pytest

from sim_core.persistence.db import execute_daily_commit, run_analytics_query
from sim_core.persistence.world_goddess import WorldGoddessCritic
from sim_core.schemas import CommitProposal


def test_conception_rbac_validation():
    """Verifies gender rules and Dragon form constraints on CONCEPTION."""
    critic = WorldGoddessCritic()

    # 1. Reject same-gender mating: BOY + BOY
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

    # 2. Reject same-gender mating: GIRL + GIRL
    prop_girl_girl = CommitProposal(
        proposal_id="prop_02",
        tick=101,
        kind="CONCEPTION",
        payload={
            "parent1_gender": "GIRL",
            "parent2_gender": "GIRL",
            "parent1_race": "HUMAN",
            "parent2_race": "HUMAN",
        },
    )
    v2 = critic.evaluate(prop_girl_girl)
    assert v2.status == "FAILURE"
    assert "one BOY and one GIRL" in v2.reason

    # 3. Reject TRUE_DRAGON mating
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

    # 4. Approve valid opposite-gender HUMANOID_DRAGON mating
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
            "conception_roll": 0.40,  # <= 0.50 cross-species conception succeeds
        },
    )
    v4 = critic.evaluate(prop_valid)
    assert v4.status == "SUCCESS"


def test_library_and_elder_governance():
    """Verifies Elder Council quorum rule (>50%), nation elder caps, and God bypass."""
    critic = WorldGoddessCritic()

    # 1. Mortal edit without Elder quorum must be rejected
    prop_mortal = CommitProposal(
        proposal_id="lib_01",
        tick=200,
        kind="LIBRARY_ENTRY",
        payload={
            "author_id": "mortal_scholar",
            "topic": "agriculture",
            "elder_approvals_count": 2,
            "total_appointed_elders": 4,  # 2 of 4 is exactly 50%, NOT > 50%
            "author_proficiency": 0.85,
        },
    )
    v1 = critic.evaluate(prop_mortal)
    assert v1.status == "FAILURE"
    assert ">50% Council of Elders" in v1.reason

    # 2. Mortal edit with strict majority (>50%) approved
    prop_approved = CommitProposal(
        proposal_id="lib_02",
        tick=201,
        kind="LIBRARY_ENTRY",
        payload={
            "author_id": "mortal_scholar",
            "topic": "agriculture",
            "elder_approvals_count": 3,
            "total_appointed_elders": 4,  # 3 of 4 is 75% > 50%
            "author_proficiency": 0.85,
        },
    )
    v2 = critic.evaluate(prop_approved)
    assert v2.status == "SUCCESS"

    # 3. Nation appointing a 3rd Library Elder must be rejected
    prop_3rd_elder = CommitProposal(
        proposal_id="settle_01",
        tick=202,
        kind="SETTLEMENT_UPDATE",
        payload={
            "sub_action": "APPOINT_LIBRARY_ELDER",
            "nation_id": "nation_solis",
            "current_nation_elders_count": 2,  # Already at maximum 2
            "target_elder_id": "elder_candidate",
        },
    )
    v3 = critic.evaluate(prop_3rd_elder)
    assert v3.status == "FAILURE"
    assert "maximum 2 Library Elders" in v3.reason

    # 4. God bypass (e.g. GOD_LIBRARY_EDIT from Godot 2D modal) succeeds unconditionally
    prop_god = CommitProposal(
        proposal_id="god_lib_01",
        tick=203,
        kind="LIBRARY_ENTRY",
        bypass_god_check=True,
        payload={"topic": "divine_truth", "content": "Direct revelation"},
    )
    v4 = critic.evaluate(prop_god)
    assert v4.status == "SUCCESS"
    assert "divine bypass granted" in v4.reason


def test_credit_transfer_double_entry_protection():
    """Verifies double-entry closed-loop debit/credit rule."""
    critic = WorldGoddessCritic()

    # 1. Insufficient funds
    prop_insufficient = CommitProposal(
        proposal_id="tx_01",
        tick=300,
        kind="CREDIT_TRANSFER",
        payload={"sender_credits": 25.0, "amount": 50.0},
    )
    v1 = critic.evaluate(prop_insufficient)
    assert v1.status == "FAILURE"
    assert "insufficient funds" in v1.reason

    # 2. Non-positive amount
    prop_zero = CommitProposal(
        proposal_id="tx_02",
        tick=301,
        kind="CREDIT_TRANSFER",
        payload={"sender_credits": 100.0, "amount": 0.0},
    )
    v2 = critic.evaluate(prop_zero)
    assert v2.status == "FAILURE"
    assert "non-positive" in v2.reason

    # 3. Valid transfer
    prop_valid = CommitProposal(
        proposal_id="tx_03",
        tick=302,
        kind="CREDIT_TRANSFER",
        payload={"sender_credits": 100.0, "amount": 40.0},
    )
    v3 = critic.evaluate(prop_valid)
    assert v3.status == "SUCCESS"


def test_judiciary_self_defense_and_war_protection():
    """Verifies that domestic/neutral courts CANNOT convict verified self-defense or active war."""
    critic = WorldGoddessCritic()

    # 1. Attempt to convict verified SELF_DEFENSE with BANISHMENT -> REJECTED
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

    # 2. Attempt to fine verified ACTIVE_WAR combatant -> REJECTED
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

    # 3. Acquittal of verified SELF_DEFENSE -> APPROVED
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
    v3 = critic.evaluate(prop_acquit)
    assert v3.status == "SUCCESS"


def test_sqlite_atomic_commit_full_rollback_on_error(test_db_path: Path):
    """
    Acceptance Requirement:
    Proves that a mid-commit failure triggers full ROLLBACK (zero partial rows written).
    """
    # Verify initial empty table
    with sqlite3.connect(test_db_path) as conn:
        count_before = conn.execute("SELECT count(*) FROM settlements").fetchone()[0]
    assert count_before == 0

    # Batch with 1 valid insert followed by a deliberate SQL syntax/constraint failure
    statements = [
        (
            (
                "INSERT INTO settlements (settlement_id, name, tier, regime_type, founder_id, "
                "center_pos_json, border_parcel_ids_json, treasury_credits, tax_rate, laws_json, "
                "at_war_with_json, allied_with_json, founded_tick) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            ),
            (
                "set_001", "Solaria", "VILLAGE", "ELECTED", "agt_01",
                "{}", "[]", 100.0, 0.05, "{}", "[]", "[]", 1,
            ),
        ),
        (
            # Deliberate error: non-existent table causing transaction failure
            "INSERT INTO non_existent_table_will_fail VALUES (1, 2, 3)",
            (),
        ),
    ]

    # Execute commit -> MUST raise exception
    with pytest.raises(sqlite3.OperationalError):
        execute_daily_commit(test_db_path, statements)

    # Verify that settlement "Solaria" was NOT partially committed (full ROLLBACK)
    with sqlite3.connect(test_db_path) as conn:
        count_after = conn.execute("SELECT count(*) FROM settlements").fetchone()[0]
    assert count_after == 0, "Atomic commit must leave zero partial rows on failure"


def test_duckdb_read_only_attach_analytics(test_db_path: Path):
    """
    Acceptance Requirement:
    Proves DuckDB read-only attach queries civ.fatalities and civ.agents without locking SQLite.
    """
    # Populate real test rows in SQLite
    statements = [
        (
            "INSERT INTO agents (agent_id, slot_idx, display_name, dynasty_surname, gender, race, "
            "godmother_affinities_json, skin_hsv_json, stage, age_ticks, health, max_health, "
            "hunger, stamina, credits, credit_score, parent_ids_json, alive, pos_json, "
            "traits_json, skills_json, tradition_ids_json, updated_tick) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "agt_01", 0, "Eldrin", "Leaf", "BOY", "ELF",
                "{}", "[0,0,0]", "ADULT", 100, 95.0, 95.0,
                100.0, 100.0, 50.0, 700.0, "[]", 1, "{}",
                "{}", "{}", "[]", 100,
            ),
        ),
        (
            "INSERT INTO fatalities (agent_id, display_name, race, age_ticks, stage_at_death, "
            "cause, season, death_day, death_tick) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("agt_99", "MortalOld", "HUMAN", 50000, "ELDER", "OLD_AGE", "WINTER", 5, 54000),
        ),
    ]
    execute_daily_commit(test_db_path, statements)

    # Query agents via DuckDB read-only attach
    rows_agents = run_analytics_query(
        test_db_path,
        "SELECT race, gender, credits FROM civ.agents WHERE alive = 1",
    )
    assert len(rows_agents) == 1
    assert rows_agents[0]["race"] == "ELF"
    assert rows_agents[0]["credits"] == 50.0

    # Query fatalities via DuckDB read-only attach
    rows_fatalities = run_analytics_query(
        test_db_path,
        "SELECT race, cause, season FROM civ.fatalities WHERE cause = 'OLD_AGE'",
    )
    assert len(rows_fatalities) == 1
    assert rows_fatalities[0]["race"] == "HUMAN"
    assert rows_fatalities[0]["season"] == "WINTER"


def test_five_daughter_voting_math_and_demon_rbac():
    """
    Acceptance Requirement for 5-Daughter Governance Math & DEMON RBAC (v3.0):
    - Library Daughters-alone: >= 3/5 approvals succeed; 2/5 fails.
    - Mortal Library Proposal: >= 3/5 God-Mother objections block it; < 3 objections allow it.
    - Divine Codex text decree: World Goddess + >= 3/5 Daughters succeeds; 2/5 fails.
    - Divine Codex parameter proposal to God: 5/5 unanimous Daughters succeeds; 4/5 fails.
    - Demon CONCEPTION: BOY DEMON + GIRL HUMAN succeeds; BOY DEMON + BOY DEMON fails.
    """
    critic = WorldGoddessCritic()

    # 1. Library Daughters-alone: 3/5 succeeds, 2/5 fails
    prop_lib_3of5 = CommitProposal(
        proposal_id="prop_lib_3",
        tick=100,
        actor_id="gm_demon",
        kind="LIBRARY_ENTRY",
        payload={"author_type": "DAUGHTERS", "daughter_approvals_count": 3},
    )
    v_lib_3 = critic.evaluate(prop_lib_3of5)
    assert v_lib_3.status == "SUCCESS"

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

    # 2. Mortal proposal blocked by >= 3/5 God-Mother objections
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
    v_mortal_blk = critic.evaluate(prop_mortal_blocked)
    assert v_mortal_blk.status == "FAILURE"
    assert "blocked by Daughters" in v_mortal_blk.reason

    prop_mortal_ok = CommitProposal(
        proposal_id="prop_mortal_ok",
        tick=103,
        kind="LIBRARY_ENTRY",
        payload={
            "author_id": "scholar_1",
            "elder_approvals_count": 3,
            "total_appointed_elders": 4,
            "godmother_approvals_count": 1,
            "godmother_objections_count": 2,
            "author_proficiency": 0.85,
        },
    )
    v_mortal_ok = critic.evaluate(prop_mortal_ok)
    assert v_mortal_ok.status == "SUCCESS"

    # 3. Divine Codex non-mechanical decree: World Goddess + >= 3/5 Daughters
    prop_codex_3of5 = CommitProposal(
        proposal_id="prop_codex_3",
        tick=104,
        actor_id="world_goddess",
        kind="DIVINE_CODEX_DECREE",
        payload={"daughter_approvals_count": 3, "content": "Decree of Concord"},
    )
    v_codex_3 = critic.evaluate(prop_codex_3of5)
    assert v_codex_3.status == "SUCCESS"

    prop_codex_2of5 = CommitProposal(
        proposal_id="prop_codex_2",
        tick=105,
        actor_id="world_goddess",
        kind="DIVINE_CODEX_DECREE",
        payload={"daughter_approvals_count": 2, "content": "Decree of Concord"},
    )
    v_codex_2 = critic.evaluate(prop_codex_2of5)
    assert v_codex_2.status == "FAILURE"
    assert ">=3/5 Daughters" in v_codex_2.reason

    # 4. Divine Codex parameter proposal to God: 5/5 unanimous succeeds, 4/5 fails
    prop_param_5of5 = CommitProposal(
        proposal_id="prop_param_5",
        tick=106,
        actor_id="gm_demon",
        kind="DIVINE_CODEX_PROPOSAL",
        payload={
            "proposer_slot": "gm_demon",
            "co_sponsors": ["gm_human", "gm_elf", "gm_dragon", "gm_beasthuman"],
            "parameter_key": "DIVINE_TRUCE_DURATION_TICKS",
            "new_value": 80000,
        },
    )
    v_param_5 = critic.evaluate(prop_param_5of5)
    assert v_param_5.status == "SUCCESS"

    prop_param_4of5 = CommitProposal(
        proposal_id="prop_param_4",
        tick=107,
        actor_id="gm_demon",
        kind="DIVINE_CODEX_PROPOSAL",
        payload={
            "proposer_slot": "gm_demon",
            "co_sponsors": ["gm_human", "gm_elf", "gm_dragon"],  # Only 4 total daughters
            "parameter_key": "DIVINE_TRUCE_DURATION_TICKS",
            "new_value": 80000,
        },
    )
    v_param_4 = critic.evaluate(prop_param_4of5)
    assert v_param_4.status == "FAILURE"
    assert "unanimous 5/5 Daughters" in v_param_4.reason

    # 5. DEMON CONCEPTION
    prop_demon_valid = CommitProposal(
        proposal_id="prop_concep_demon",
        tick=108,
        kind="CONCEPTION",
        payload={
            "parent1_gender": "BOY",
            "parent1_race": "DEMON",
            "parent2_gender": "GIRL",
            "parent2_race": "HUMAN",
            "conception_roll": 0.45,
        },
    )
    v_demon_valid = critic.evaluate(prop_demon_valid)
    assert v_demon_valid.status == "SUCCESS"

    prop_demon_same = CommitProposal(
        proposal_id="prop_concep_same",
        tick=109,
        kind="CONCEPTION",
        payload={
            "parent1_gender": "BOY",
            "parent1_race": "DEMON",
            "parent2_gender": "BOY",
            "parent2_race": "DEMON",
        },
    )
    v_demon_same = critic.evaluate(prop_demon_same)
    assert v_demon_same.status == "FAILURE"

