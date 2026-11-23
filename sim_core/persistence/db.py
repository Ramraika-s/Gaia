"""
sim_core/persistence/db.py
SQLite WAL persistence engine and DuckDB read-only analytics helper for Gaia.
Executed exclusively by the World Goddess during atomic daily Two-Phase Commits.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

import duckdb

DDL_SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA temp_store = MEMORY;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS world_meta (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS divine_entities (
    slot TEXT PRIMARY KEY,
    bestowed_name TEXT NOT NULL,
    role TEXT NOT NULL,
    patron_race TEXT,
    divine_energy REAL NOT NULL,
    personality_json TEXT NOT NULL,
    oracle_agent_ids_json TEXT NOT NULL,
    active_truce_with_json TEXT NOT NULL,
    intervention_cooldown_until_tick INTEGER NOT NULL DEFAULT 0,
    covenant_rebukes INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sister_council_messages (
    message_id TEXT PRIMARY KEY,
    day INTEGER NOT NULL,
    tick INTEGER NOT NULL,
    sender_slot TEXT NOT NULL,
    recipient_slots_json TEXT NOT NULL,
    topic TEXT NOT NULL,
    summary TEXT NOT NULL,
    resolution TEXT
);

CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    slot_idx INTEGER NOT NULL,
    display_name TEXT NOT NULL,
    dynasty_surname TEXT NOT NULL,
    epithet TEXT,
    gender TEXT NOT NULL,
    race TEXT NOT NULL,
    sub_lineage TEXT,
    secondary_heritage_race TEXT,
    dragon_form TEXT,
    patron_godmother_slot TEXT,
    godmother_affinities_json TEXT NOT NULL,
    is_oracle INTEGER NOT NULL DEFAULT 0,
    skin_hsv_json TEXT NOT NULL,
    settlement_id TEXT,
    nation_id TEXT,
    religion_id TEXT,
    cleric_rank TEXT NOT NULL DEFAULT 'NONE',
    stage TEXT NOT NULL,
    age_ticks INTEGER NOT NULL,
    health REAL NOT NULL,
    max_health REAL NOT NULL,
    hunger REAL NOT NULL,
    stamina REAL NOT NULL,
    injured REAL NOT NULL DEFAULT 0.0,
    illness REAL NOT NULL DEFAULT 0.0,
    distress REAL NOT NULL DEFAULT 0.0,
    crying INTEGER NOT NULL DEFAULT 0,
    credits REAL NOT NULL,
    credit_score REAL NOT NULL,
    breeding_cooldown INTEGER NOT NULL DEFAULT 0,
    pregnant_ticks_remaining INTEGER NOT NULL DEFAULT 0,
    pregnancy_father_id TEXT,
    is_cross_species_pregnancy INTEGER NOT NULL DEFAULT 0,
    last_prayer_tick INTEGER NOT NULL DEFAULT 0,
    parent_ids_json TEXT NOT NULL,
    spouse_id TEXT,
    alive INTEGER NOT NULL,
    quarantined INTEGER NOT NULL DEFAULT 0,
    pos_json TEXT NOT NULL,
    traits_json TEXT NOT NULL,
    skills_json TEXT NOT NULL,
    tradition_ids_json TEXT NOT NULL,
    updated_tick INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS relationships (
    agent_a TEXT NOT NULL,
    agent_b TEXT NOT NULL,
    trust REAL NOT NULL,
    affinity REAL NOT NULL,
    fear REAL NOT NULL,
    role TEXT NOT NULL,
    interaction_count INTEGER NOT NULL,
    PRIMARY KEY (agent_a, agent_b)
);

CREATE TABLE IF NOT EXISTS settlements (
    settlement_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    tier TEXT NOT NULL,
    parent_polity_id TEXT,
    regime_type TEXT NOT NULL,
    is_holy_polity INTEGER NOT NULL DEFAULT 0,
    is_neutral_free_city INTEGER NOT NULL DEFAULT 0,
    war_exempt INTEGER NOT NULL DEFAULT 0,
    state_religion_id TEXT,
    founder_id TEXT NOT NULL,
    leader_id TEXT,
    center_pos_json TEXT NOT NULL,
    border_parcel_ids_json TEXT NOT NULL,
    treasury_credits REAL NOT NULL,
    tax_rate REAL NOT NULL,
    tariff_rate REAL NOT NULL DEFAULT 0.0,
    next_election_tick INTEGER,
    laws_json TEXT NOT NULL,
    at_war_with_json TEXT NOT NULL,
    allied_with_json TEXT NOT NULL,
    founded_tick INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS settlement_appeals (
    appeal_id TEXT PRIMARY KEY,
    settlement_id TEXT NOT NULL,
    proposer_id TEXT NOT NULL,
    appeal_kind TEXT NOT NULL,
    current_tier TEXT,
    requested_tier TEXT,
    claimed_parcel_ids_json TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT NOT NULL,
    submitted_tick INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS settlement_standing (
    settlement_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    standing REAL NOT NULL,
    PRIMARY KEY (settlement_id, agent_id)
);

CREATE TABLE IF NOT EXISTS religions (
    religion_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    aligned_deity_slot TEXT NOT NULL,
    founder_id TEXT NOT NULL,
    pope_id TEXT,
    treasury_credits REAL NOT NULL,
    tenets_json TEXT NOT NULL,
    canonized_entry_ids_json TEXT NOT NULL,
    excommunicated_ids_json TEXT NOT NULL,
    founded_tick INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS parcels (
    parcel_id TEXT PRIMARY KEY,
    cx INTEGER NOT NULL,
    cz INTEGER NOT NULL,
    settlement_id TEXT,
    nation_id TEXT,
    owner_id TEXT,
    owner_type TEXT NOT NULL,
    has_altar INTEGER NOT NULL DEFAULT 0,
    has_library INTEGER NOT NULL DEFAULT 0,
    assessed_value REAL NOT NULL,
    for_sale_price REAL,
    tenant_id TEXT,
    rent_per_civic_tick REAL NOT NULL DEFAULT 0.0,
    updated_tick INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS world_bank_loans (
    loan_id TEXT PRIMARY KEY,
    holder_id TEXT NOT NULL,
    holder_type TEXT NOT NULL,
    principal REAL NOT NULL,
    remaining_balance REAL NOT NULL,
    interest_rate REAL NOT NULL,
    missed_windows INTEGER NOT NULL,
    status TEXT NOT NULL,
    issued_tick INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS wtc_history (
    tick INTEGER PRIMARY KEY,
    day INTEGER NOT NULL,
    cpi REAL NOT NULL,
    money_supply_m REAL NOT NULL,
    real_output_q REAL NOT NULL,
    prices_json TEXT NOT NULL,
    frozen INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS judiciary_cases (
    case_id TEXT PRIMARY KEY,
    settlement_id TEXT,
    accused_id TEXT NOT NULL,
    victim_id TEXT,
    offense_type TEXT NOT NULL,
    combat_context TEXT,
    witness_ids_json TEXT NOT NULL,
    evidence_score REAL NOT NULL,
    status TEXT NOT NULL,
    ruling TEXT,
    penalty_credits REAL NOT NULL,
    opened_tick INTEGER NOT NULL,
    closed_tick INTEGER
);

CREATE TABLE IF NOT EXISTS criminal_records (
    record_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    settlement_id TEXT,
    offense_type TEXT NOT NULL,
    ruling TEXT NOT NULL,
    penalty_credits REAL NOT NULL,
    active_warrant INTEGER NOT NULL DEFAULT 0,
    recorded_tick INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS fatalities (
    agent_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    race TEXT NOT NULL,
    sub_lineage TEXT,
    secondary_heritage_race TEXT,
    age_ticks INTEGER NOT NULL,
    stage_at_death TEXT NOT NULL,
    cause TEXT NOT NULL,
    combat_context TEXT,
    killer_id TEXT,
    settlement_id TEXT,
    season TEXT NOT NULL,
    death_day INTEGER NOT NULL,
    death_tick INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS world_library (
    entry_id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    author_id TEXT NOT NULL,
    author_proficiency REAL NOT NULL,
    skill_bonus REAL NOT NULL,
    is_scripture INTEGER NOT NULL DEFAULT 0,
    read_count INTEGER NOT NULL DEFAULT 0,
    created_tick INTEGER NOT NULL,
    subject TEXT,
    section TEXT,
    fact_key TEXT,
    tags_json TEXT,
    mechanical_effects_json TEXT,
    author_type TEXT DEFAULT 'MORTAL'
);

CREATE TABLE IF NOT EXISTS library_council_elders (
    nation_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    appointed_tick INTEGER NOT NULL,
    PRIMARY KEY (nation_id, agent_id)
);

CREATE TABLE IF NOT EXISTS library_proposals (
    proposal_id TEXT PRIMARY KEY,
    action TEXT NOT NULL,
    target_entry_id TEXT,
    author_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    author_proficiency REAL NOT NULL,
    votes_approve_json TEXT NOT NULL,
    votes_reject_json TEXT NOT NULL,
    godmother_approvals_json TEXT NOT NULL,
    godmother_objections_json TEXT NOT NULL,
    first_approval_tick INTEGER,
    appeal_target TEXT,
    appeal_ruling TEXT,
    status TEXT NOT NULL,
    created_tick INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS divine_codex (
    entry_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    category TEXT NOT NULL,
    parameter_key TEXT,
    parameter_value_json TEXT,
    author_slot TEXT NOT NULL,
    supporting_daughter_slots_json TEXT NOT NULL,
    approved_by_god INTEGER NOT NULL DEFAULT 0,
    created_tick INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS divine_codex_proposals (
    proposal_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    parameter_key TEXT NOT NULL,
    parameter_value_json TEXT NOT NULL,
    proposer_slot TEXT NOT NULL,
    co_sponsors_json TEXT NOT NULL,
    status TEXT NOT NULL,
    submitted_tick INTEGER NOT NULL,
    resolved_tick INTEGER
);

CREATE TABLE IF NOT EXISTS traditions (
    tradition_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    origin_settlement_id TEXT NOT NULL,
    trigger TEXT NOT NULL,
    ritual_action TEXT NOT NULL,
    adoption_rate REAL NOT NULL,
    taboo_penalty REAL NOT NULL,
    created_tick INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS political_history (
    event_id TEXT PRIMARY KEY,
    settlement_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    winner_or_actor_id TEXT,
    details_json TEXT NOT NULL,
    tick INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS healer_incidents (
    incident_id TEXT PRIMARY KEY,
    day INTEGER NOT NULL,
    tick INTEGER NOT NULL,
    fault_class TEXT NOT NULL,
    agent_id TEXT,
    action_taken TEXT NOT NULL,
    escalated INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS world_goddess_audit (
    proposal_id TEXT PRIMARY KEY,
    tick INTEGER NOT NULL,
    kind TEXT NOT NULL,
    actor_id TEXT,
    status TEXT NOT NULL,
    reason TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agents_alive ON agents(alive);
CREATE INDEX IF NOT EXISTS idx_agents_race ON agents(race, sub_lineage);
CREATE INDEX IF NOT EXISTS idx_agents_patron ON agents(patron_godmother_slot);
CREATE INDEX IF NOT EXISTS idx_agents_settlement ON agents(settlement_id);
CREATE INDEX IF NOT EXISTS idx_parcels_owner ON parcels(owner_id);
CREATE INDEX IF NOT EXISTS idx_parcels_settlement ON parcels(settlement_id);
CREATE INDEX IF NOT EXISTS idx_parcels_nation ON parcels(nation_id);
CREATE INDEX IF NOT EXISTS idx_fatalities_race_cause_season ON fatalities(race, cause, season);
CREATE INDEX IF NOT EXISTS idx_cases_status ON judiciary_cases(status);
CREATE INDEX IF NOT EXISTS idx_crimes_agent ON criminal_records(agent_id);
CREATE INDEX IF NOT EXISTS idx_library_topic ON world_library(topic);
CREATE INDEX IF NOT EXISTS idx_council_day ON sister_council_messages(day);
CREATE INDEX IF NOT EXISTS idx_healer_day_class ON healer_incidents(day, fault_class);
"""


def init_db(db_path: str | Path) -> None:
    """Initializes the SQLite WAL database with the complete v3.0 schema."""
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(p) as conn:
        conn.executescript(DDL_SCHEMA)
        cursor = conn.cursor()
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


def execute_daily_commit(
    db_path: str | Path,
    statements: list[tuple[str, tuple[Any, ...]]],
) -> None:
    """
    Executes a list of SQL statements inside a single BEGIN IMMEDIATE ... COMMIT transaction.
    If ANY error occurs, rolls back immediately so zero partial rows persist.
    """
    p = Path(db_path)
    conn = sqlite3.connect(p)
    try:
        conn.execute("BEGIN IMMEDIATE")
        for sql, params in statements:
            conn.execute(sql, params)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def run_analytics_query(db_path: str | Path, sql: str) -> list[dict[str, Any]]:
    """
    Attaches data/civilization.db read-only inside DuckDB and executes an analytical query
    without acquiring write locks on the SQLite database.
    """
    path_str = os.path.abspath(str(db_path))
    con = duckdb.connect(":memory:")
    try:
        con.execute(f"ATTACH '{path_str}' AS civ (TYPE sqlite, READ_ONLY);")
        rel = con.execute(sql)
        if rel.description is None:
            return []
        cols = [d[0] for d in rel.description]
        return [dict(zip(cols, r, strict=False)) for r in rel.fetchall()]
    finally:
        con.close()
