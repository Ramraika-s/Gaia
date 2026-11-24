"""
sim_core/persistence/state_serializer.py
Dedicated WorldStateSerializer for Gaia civilization simulation:
- build_daily_sql_deltas(engine): Converts entire live RAM simulation state into
  an atomic list of SQLite SQL deltas.
- restore_engine_state(engine, db_path, pt_state): Rebuilds entire live RAM
  simulation from SQLite database and PyTorch tensor checkpoint, including
  clean resets of adapter and navigation, and full reconstruction of Palace Knight
  and City Guard patrol rosters.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from sim_core.brains.personality import MoodState, PersonalityVector
from sim_core.schemas import (
    AgentRecord,
    BuildingRecord,
    BuildingType,
    DeitySlot,
    DivineCodexEntry,
    DivineCodexProposalRecord,
    FatalityRecord,
    JudiciaryCaseRecord,
    ParcelRecord,
    RacialStyle,
    ReligionRecord,
    SettlementRecord,
    SettlementTier,
    Vec3,
    WorldLibraryEntry,
)
from sim_core.society.politics import Polity

if TYPE_CHECKING:
    from sim_core.engine import SimulationEngine


class WorldStateSerializer:
    """Handles bidirectional serialization between live SimulationEngine RAM and SQLite/PyTorch."""

    @staticmethod
    def build_daily_sql_deltas(engine: SimulationEngine) -> list[tuple[str, tuple[Any, ...]]]:
        """Serializes all engine subsystems into an atomic batch of SQLite statements."""
        sql_deltas: list[tuple[str, tuple[Any, ...]]] = []

        # 1. world_meta
        meta_items: list[tuple[str, str]] = [
            ("current_day", str(engine.current_day)),
            ("current_tick", str(engine.current_tick)),
            ("current_season", json.dumps(engine.current_season)),
            ("reserve_credits", str(engine.bank.reserve_credits)),
            ("wtc_cpi", str(engine.wtc.cpi)),
            ("wtc_base_m", str(engine.wtc.base_m)),
            ("wtc_base_q", str(engine.wtc.base_q)),
            ("wtc_frozen", "1" if engine.wtc.frozen else "0"),
            ("wtc_current_prices", json.dumps(engine.wtc.current_prices)),
            ("live_engine_overrides", json.dumps(engine.governance_engine.live_engine_overrides)),
        ]
        for mk, mv in meta_items:
            sql_deltas.append(
                ("INSERT OR REPLACE INTO world_meta (key, value_json) VALUES (?, ?)", (mk, mv))
            )

        # 2. divine_entities
        for entity in engine.divine_hierarchy.entities.values():
            p_vec_json = (
                entity.personality_vector.model_dump_json()
                if entity.personality_vector
                else None
            )
            mood_json = entity.mood.model_dump_json() if entity.mood else None
            sql_deltas.append(
                (
                    "INSERT OR REPLACE INTO divine_entities ("
                    "slot, bestowed_name, role, patron_race, divine_energy, personality_json, "
                    "oracle_agent_ids_json, active_truce_with_json, "
                    "intervention_cooldown_until_tick, covenant_rebukes, personality_vector_json, "
                    "mood_json"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        entity.slot,
                        entity.bestowed_name,
                        entity.role,
                        entity.patron_race,
                        entity.divine_energy,
                        entity.personality.model_dump_json(),
                        json.dumps(entity.oracle_agent_ids),
                        json.dumps(entity.active_truce_with),
                        entity.intervention_cooldown_until_tick,
                        entity.covenant_rebukes,
                        p_vec_json,
                        mood_json,
                    ),
                )
            )

        # 3. agents
        for agent in engine.agents.values():
            sql_deltas.append(
                (
                    "INSERT OR REPLACE INTO agents ("
                    "agent_id, slot_idx, display_name, dynasty_surname, epithet, gender, race, "
                    "sub_lineage, secondary_heritage_race, dragon_form, patron_godmother_slot, "
                    "godmother_affinities_json, is_oracle, skin_hsv_json, settlement_id, "
                    "nation_id, religion_id, cleric_rank, stage, age_ticks, health, max_health, "
                    "hunger, stamina, injured, illness, distress, crying, credits, credit_score, "
                    "breeding_cooldown, pregnant_ticks_remaining, pregnancy_father_id, "
                    "is_cross_species_pregnancy, last_prayer_tick, parent_ids_json, spouse_id, "
                    "alive, quarantined, pos_json, traits_json, skills_json, tradition_ids_json, "
                    "updated_tick, role, title, yaw, profession, profession_level, profession_xp, "
                    "hygiene, fatigue, known_books_json, personality_json, mood_json, "
                    "active_mechanical_effects_json, equipped_gear_json, home_building_id"
                    ") VALUES ("
                    "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                    "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                    "?, ?, ?, ?, ?, ?, ?, ?, ?, ?"
                    ")",
                    (
                        agent.agent_id,
                        agent.slot_idx,
                        agent.display_name,
                        agent.dynasty_surname,
                        agent.epithet,
                        agent.gender,
                        agent.race,
                        agent.sub_lineage,
                        agent.secondary_heritage_race,
                        agent.dragon_form,
                        agent.patron_godmother_slot,
                        json.dumps(agent.godmother_affinities),
                        1 if agent.is_oracle else 0,
                        json.dumps(agent.skin_hsv),
                        agent.settlement_id,
                        agent.nation_id,
                        agent.religion_id,
                        agent.cleric_rank,
                        agent.stage,
                        agent.age_ticks,
                        agent.health,
                        agent.max_health,
                        agent.hunger,
                        agent.stamina,
                        agent.injured,
                        agent.illness,
                        agent.distress,
                        1 if agent.crying else 0,
                        agent.credits,
                        agent.credit_score,
                        agent.breeding_cooldown,
                        agent.pregnant_ticks_remaining,
                        agent.pregnancy_father_id,
                        1 if agent.is_cross_species_pregnancy else 0,
                        agent.last_prayer_tick,
                        json.dumps(agent.parent_ids),
                        agent.spouse_id,
                        1 if agent.alive else 0,
                        1 if agent.quarantined else 0,
                        agent.pos.model_dump_json(),
                        json.dumps(agent.traits),
                        json.dumps(agent.skills),
                        json.dumps(agent.tradition_ids),
                        engine.current_tick,
                        agent.role,
                        agent.title,
                        agent.yaw,
                        agent.profession,
                        agent.profession_level,
                        agent.profession_xp,
                        agent.hygiene,
                        agent.fatigue,
                        json.dumps(agent.known_books),
                        agent.personality.model_dump_json() if agent.personality else None,
                        agent.mood.model_dump_json() if agent.mood else None,
                        json.dumps(agent.active_mechanical_effects),
                        json.dumps(agent.equipped_gear),
                        agent.home_building_id,
                    ),
                )
            )

        # 4. buildings (both Ring 1 city buildings & Ring 2 pioneer cabins)
        all_buildings: dict[str, BuildingRecord] = {}
        if hasattr(engine, "city_layout") and engine.city_layout:
            all_buildings.update(engine.city_layout.buildings)
        if hasattr(engine, "housing_market") and engine.housing_market:
            all_buildings.update(engine.housing_market.frontier_buildings)

        for bld in all_buildings.values():
            sql_deltas.append(
                (
                    "INSERT OR REPLACE INTO buildings ("
                    "building_id, city_id, building_type, racial_style, x, y, z, "
                    "rotation_y, parcel_x, parcel_z, footprint_radius, owner_id, "
                    "owner_name, for_sale, sale_price, settlement_id, is_frontier"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        bld.building_id,
                        bld.city_id,
                        bld.building_type,
                        bld.racial_style,
                        bld.x,
                        bld.y,
                        bld.z,
                        bld.rotation_y,
                        bld.parcel_x,
                        bld.parcel_z,
                        bld.footprint_radius,
                        bld.owner_id,
                        bld.owner_name,
                        1 if bld.for_sale else 0,
                        bld.sale_price,
                        bld.settlement_id,
                        1 if bld.is_frontier else 0,
                    ),
                )
            )

        # 5. parcels
        if hasattr(engine, "property_mgr") and engine.property_mgr:
            for parcel in engine.property_mgr.parcels.values():
                sql_deltas.append(
                    (
                        "INSERT OR REPLACE INTO parcels ("
                        "parcel_id, cx, cz, settlement_id, nation_id, owner_id, "
                        "owner_type, has_altar, has_library, assessed_value, "
                        "for_sale_price, tenant_id, rent_per_civic_tick, updated_tick"
                        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            parcel.parcel_id,
                            parcel.cx,
                            parcel.cz,
                            parcel.settlement_id,
                            parcel.nation_id,
                            parcel.owner_id,
                            parcel.owner_type,
                            1 if parcel.has_altar else 0,
                            1 if parcel.has_library else 0,
                            parcel.assessed_value,
                            parcel.for_sale_price,
                            parcel.tenant_id,
                            parcel.rent_per_civic_tick,
                            parcel.updated_tick,
                        ),
                    )
                )

        # 6. settlements (polities & frontier villages)
        all_settlements: dict[str, Any] = {}
        if hasattr(engine, "political_engine") and engine.political_engine:
            all_settlements.update(engine.political_engine.polities)
        if hasattr(engine, "housing_market") and engine.housing_market:
            all_settlements.update(engine.housing_market.frontier_villages)

        for s_obj in all_settlements.values():
            if isinstance(s_obj, SettlementRecord):
                sql_deltas.append(
                    (
                        "INSERT OR REPLACE INTO settlements ("
                        "settlement_id, name, tier, parent_polity_id, regime_type, "
                        "is_holy_polity, is_neutral_free_city, war_exempt, state_religion_id, "
                        "founder_id, leader_id, center_pos_json, border_parcel_ids_json, "
                        "treasury_credits, tax_rate, tariff_rate, next_election_tick, "
                        "laws_json, at_war_with_json, allied_with_json, founded_tick"
                        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            s_obj.settlement_id,
                            s_obj.name,
                            s_obj.tier,
                            s_obj.parent_polity_id,
                            s_obj.regime_type,
                            1 if s_obj.is_holy_polity else 0,
                            1 if s_obj.is_neutral_free_city else 0,
                            1 if s_obj.war_exempt else 0,
                            s_obj.state_religion_id,
                            s_obj.founder_id,
                            s_obj.leader_id,
                            json.dumps(s_obj.center_pos.model_dump()),
                            json.dumps(s_obj.border_parcel_ids),
                            s_obj.treasury_credits,
                            s_obj.tax_rate,
                            s_obj.tariff_rate,
                            s_obj.next_election_tick,
                            json.dumps(s_obj.laws),
                            json.dumps(s_obj.at_war_with),
                            json.dumps(s_obj.allied_with),
                            s_obj.founded_tick,
                        ),
                    )
                )
            else:
                # Polity instance
                sql_deltas.append(
                    (
                        "INSERT OR REPLACE INTO settlements ("
                        "settlement_id, name, tier, parent_polity_id, regime_type, "
                        "is_holy_polity, is_neutral_free_city, war_exempt, state_religion_id, "
                        "founder_id, leader_id, center_pos_json, border_parcel_ids_json, "
                        "treasury_credits, tax_rate, tariff_rate, next_election_tick, "
                        "laws_json, at_war_with_json, allied_with_json, founded_tick"
                        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            s_obj.settlement_id,
                            s_obj.name,
                            s_obj.tier,
                            None,
                            s_obj.regime_type,
                            0,
                            1 if s_obj.is_neutral_free_city else 0,
                            1 if s_obj.war_exempt else 0,
                            None,
                            "system_founder",
                            s_obj.leader_id,
                            json.dumps({"x": 0.0, "y": 0.0, "z": 0.0}),
                            json.dumps(list(getattr(s_obj, "border_parcels", []))),
                            s_obj.treasury_credits,
                            s_obj.tax_rate,
                            s_obj.tariff_rate,
                            None,
                            "[]",
                            json.dumps(list(getattr(s_obj, "at_war_with", []))),
                            json.dumps(list(getattr(s_obj, "allied_with", []))),
                            0,
                        ),
                    )
                )

        # 7. religions
        for rel in engine.religion_mgr.religions.values():
            sql_deltas.append(
                (
                    "INSERT OR REPLACE INTO religions ("
                    "religion_id, name, aligned_deity_slot, founder_id, pope_id, "
                    "treasury_credits, tenets_json, canonized_entry_ids_json, "
                    "excommunicated_ids_json, founded_tick"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        rel.religion_id,
                        rel.name,
                        rel.aligned_deity_slot,
                        rel.founder_id,
                        rel.pope_id,
                        rel.treasury_credits,
                        json.dumps(rel.tenets),
                        json.dumps(rel.canonized_entry_ids),
                        json.dumps(rel.excommunicated_ids),
                        rel.founded_tick,
                    ),
                )
            )

        # 8. judiciary_cases & criminal_records
        for case in engine.judiciary.cases.values():
            sql_deltas.append(
                (
                    "INSERT OR REPLACE INTO judiciary_cases ("
                    "case_id, settlement_id, accused_id, victim_id, offense_type, "
                    "combat_context, witness_ids_json, evidence_score, status, ruling, "
                    "penalty_credits, opened_tick, closed_tick"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        case.case_id,
                        case.settlement_id,
                        case.accused_id,
                        case.victim_id,
                        case.offense_type,
                        case.combat_context,
                        json.dumps(case.witness_ids),
                        case.evidence_score,
                        case.status,
                        case.ruling,
                        case.penalty_credits,
                        case.opened_tick,
                        case.closed_tick,
                    ),
                )
            )

        for ag_id, case_ids in engine.judiciary.criminal_records.items():
            for c_id in case_ids:
                sql_deltas.append(
                    (
                        "INSERT OR IGNORE INTO criminal_records (agent_id, case_id) VALUES (?, ?)",
                        (ag_id, c_id),
                    )
                )

        # 9. fatalities
        for f in engine.judiciary.fatality_index:
            sql_deltas.append(
                (
                    "INSERT OR REPLACE INTO fatalities ("
                    "agent_id, display_name, race, sub_lineage, secondary_heritage_race, "
                    "age_ticks, stage_at_death, cause, combat_context, killer_id, "
                    "settlement_id, season, death_day, death_tick"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        f.agent_id,
                        f.display_name,
                        f.race,
                        f.sub_lineage,
                        f.secondary_heritage_race,
                        f.age_ticks,
                        f.stage_at_death,
                        f.cause,
                        f.combat_context,
                        f.killer_id,
                        f.settlement_id,
                        f.season,
                        f.death_day,
                        f.death_tick,
                    ),
                )
            )

        # 10. world_library
        for book in engine.governance_engine.library_entries.values():
            tags_json = json.dumps(book.tags) if book.tags else "[]"
            effects_json = json.dumps(book.mechanical_effects) if book.mechanical_effects else "{}"
            body_text = getattr(book, "body", None) or book.summary
            if isinstance(book, WorldLibraryEntry):
                sql_deltas.append(
                    (
                        "INSERT OR REPLACE INTO world_library ("
                        "entry_id, topic, title, summary, author_id, "
                        "author_proficiency, skill_bonus, is_scripture, read_count, "
                        "created_tick, subject, section, fact_key, tags_json, "
                        "mechanical_effects_json, author_type, body"
                        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            book.entry_id,
                            book.topic,
                            book.title,
                            book.summary,
                            book.author_id,
                            book.author_proficiency,
                            book.skill_bonus,
                            1 if book.is_scripture else 0,
                            book.read_count,
                            book.created_tick,
                            book.subject,
                            book.section,
                            book.fact_key,
                            tags_json,
                            effects_json,
                            book.author_type,
                            body_text,
                        ),
                    )
                )
            else:
                author_val = getattr(book, "author", "UNKNOWN")
                target_sec = getattr(book, "target_section", getattr(book, "section", ""))
                sql_deltas.append(
                    (
                        "INSERT OR REPLACE INTO world_library ("
                        "entry_id, topic, title, summary, author_id, "
                        "author_proficiency, skill_bonus, is_scripture, read_count, "
                        "created_tick, subject, section, fact_key, tags_json, "
                        "mechanical_effects_json, author_type, body"
                        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            book.entry_id,
                            book.subject,
                            book.title,
                            book.summary,
                            author_val,
                            1.0,
                            0.0,
                            0,
                            0,
                            0,
                            book.subject,
                            target_sec,
                            book.fact_key,
                            tags_json,
                            effects_json,
                            book.author_type,
                            body_text,
                        ),
                    )
                )

        # 11. divine_codex
        for decree in engine.governance_engine.codex_entries.values():
            sql_deltas.append(
                (
                    "INSERT OR REPLACE INTO divine_codex ("
                    "entry_id, title, text, category, parameter_key, parameter_value_json, "
                    "author_slot, supporting_daughter_slots_json, approved_by_god, created_tick"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        decree.entry_id,
                        decree.title,
                        decree.text,
                        decree.category,
                        decree.parameter_key,
                        decree.parameter_value_json,
                        decree.author_slot,
                        json.dumps(decree.supporting_daughter_slots),
                        1 if decree.approved_by_god else 0,
                        decree.created_tick,
                    ),
                )
            )

        # 12. divine_codex_proposals
        for prop in engine.governance_engine.codex_proposals.values():
            sql_deltas.append(
                (
                    "INSERT OR REPLACE INTO divine_codex_proposals ("
                    "proposal_id, title, text, parameter_key, parameter_value_json, "
                    "proposer_slot, co_sponsors_json, status, submitted_tick, resolved_tick"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        prop.proposal_id,
                        prop.title,
                        prop.text,
                        prop.parameter_key,
                        prop.parameter_value_json,
                        prop.proposer_slot,
                        json.dumps(prop.co_sponsors),
                        prop.status,
                        prop.submitted_tick,
                        prop.resolved_tick,
                    ),
                )
            )

        return sql_deltas

    @staticmethod
    def restore_engine_state(
        engine: SimulationEngine,
        db_path: Path,
        pt_state: dict[str, Any] | None,
    ) -> None:
        """Restores live simulation RAM state cleanly from SQLite and PyTorch tensors."""
        # 1. Reset WorldAdapter / WebSocket streaming buffers prior to restoring agents
        if hasattr(engine, "adapter") and engine.adapter:
            if hasattr(engine.adapter, "reset"):
                engine.adapter.reset()

        # 2. Reset navigation engine: clear dynamic footprints, preserving default landmarks
        if hasattr(engine, "navigation") and engine.navigation:
            if hasattr(engine.navigation, "reset_to_default_landmarks"):
                engine.navigation.reset_to_default_landmarks()

        # 3. Load PyTorch model weights & brain tensors
        if pt_state is not None:
            if "batched_net" in pt_state:
                bnet = pt_state["batched_net"]
                if isinstance(bnet, dict) and "capacity" in bnet:
                    engine.batched_net.load_state_dict_custom(bnet)
                else:
                    engine.batched_net.load_state_dict(bnet)
            if "shared_net" in pt_state:
                engine.shared_skill_net.load_state_dict(pt_state["shared_net"])
            if "hierarchical_brain" in pt_state:
                engine.hierarchical_brain.load_state_dict(pt_state["hierarchical_brain"])
            if "reserve_credits" in pt_state:
                engine.bank.reserve_credits = float(pt_state["reserve_credits"])
            if "current_day" in pt_state:
                engine.current_day = int(pt_state["current_day"])
            if "current_tick" in pt_state:
                engine.current_tick = int(pt_state["current_tick"])

        # 4. Read restored SQLite DB and rebuild all live RAM registries
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # A. world_meta
            cur.execute("SELECT key, value_json FROM world_meta;")
            meta = {r["key"]: r["value_json"] for r in cur.fetchall()}
            if "current_day" in meta:
                engine.current_day = int(meta["current_day"])
            elif "world_day" in meta:
                engine.current_day = int(meta["world_day"])
            if "current_tick" in meta:
                engine.current_tick = int(meta["current_tick"])
            if "current_season" in meta:
                engine.current_season = json.loads(meta["current_season"])
            if "reserve_credits" in meta:
                engine.bank.reserve_credits = float(meta["reserve_credits"])
            if "wtc_cpi" in meta:
                engine.wtc.cpi = float(meta["wtc_cpi"])
            if "wtc_base_m" in meta:
                engine.wtc.base_m = float(meta["wtc_base_m"])
            if "wtc_base_q" in meta:
                engine.wtc.base_q = float(meta["wtc_base_q"])
            if "wtc_frozen" in meta:
                engine.wtc.frozen = meta["wtc_frozen"] == "1"
            if "wtc_current_prices" in meta:
                try:
                    engine.wtc.current_prices = json.loads(meta["wtc_current_prices"])
                except Exception:
                    pass
            if "live_engine_overrides" in meta:
                engine.governance_engine.live_engine_overrides = json.loads(
                    meta["live_engine_overrides"]
                )

            # B. divine_entities
            cur.execute(
                "SELECT slot, bestowed_name, divine_energy, personality_json, "
                "oracle_agent_ids_json, active_truce_with_json, personality_vector_json, mood_json "
                "FROM divine_entities;"
            )
            for r in cur.fetchall():
                slot = r["slot"]
                if slot in engine.divine_hierarchy.entities:
                    ent = engine.divine_hierarchy.entities[slot]
                    ent.bestowed_name = r["bestowed_name"]
                    ent.divine_energy = float(r["divine_energy"])
                    ent.oracle_agent_ids = json.loads(r["oracle_agent_ids_json"])
                    ent.active_truce_with = json.loads(r["active_truce_with_json"])
                    if r["personality_vector_json"]:
                        ent.personality_vector = PersonalityVector.model_validate_json(
                            r["personality_vector_json"]
                        )
                    if r["mood_json"]:
                        ent.mood = MoodState.model_validate_json(r["mood_json"])
                    # Sync bestowed name into autonomous deity registry if present
                    if slot in engine.divine_autonomy.deities:
                        engine.divine_autonomy.deities[slot].name = ent.bestowed_name

            # C. agents
            cur.execute("SELECT * FROM agents;")
            engine.agents.clear()
            engine.spatial_grid.clear()
            engine.judiciary.population_ledger.clear()

            for r in cur.fetchall():
                r_dict = dict(r)
                pos_data = json.loads(r_dict.get("pos_json") or "{}")
                if pos_data:
                    pos_vec = Vec3(**pos_data)
                else:
                    pos_vec = Vec3(x=r_dict["x"], y=r_dict["y"], z=r_dict["z"])

                personality_obj = None
                if r_dict.get("personality_json"):
                    personality_obj = PersonalityVector.model_validate_json(
                        r_dict["personality_json"]
                    )

                mood_obj = None
                if r_dict.get("mood_json"):
                    mood_obj = MoodState.model_validate_json(r_dict["mood_json"])

                agent = AgentRecord(
                    agent_id=r_dict["agent_id"],
                    slot_idx=r_dict["slot_idx"],
                    display_name=r_dict["display_name"],
                    dynasty_surname=r_dict.get("dynasty_surname") or "Unknown",
                    epithet=r_dict.get("epithet"),
                    gender=r_dict["gender"],
                    race=r_dict["race"],
                    sub_lineage=r_dict.get("sub_lineage"),
                    secondary_heritage_race=r_dict.get("secondary_heritage_race"),
                    dragon_form=r_dict.get("dragon_form"),
                    role=r_dict.get("role", "CITIZEN"),
                    title=r_dict.get("title"),
                    patron_godmother_slot=r_dict.get("patron_godmother_slot"),
                    godmother_affinities=json.loads(
                        r_dict.get("godmother_affinities_json") or "{}"
                    ),
                    is_oracle=bool(r_dict.get("is_oracle", 0)),
                    skin_hsv=json.loads(r_dict.get("skin_hsv_json") or "[0.08, 0.35, 0.85]"),
                    settlement_id=r_dict.get("settlement_id"),
                    nation_id=r_dict.get("nation_id"),
                    religion_id=r_dict.get("religion_id"),
                    cleric_rank=r_dict.get("cleric_rank", "NONE"),
                    stage=r_dict.get("stage", "INFANT"),
                    age_ticks=r_dict.get("age_ticks", 0),
                    health=r_dict.get("health", 40.0),
                    max_health=r_dict.get("max_health", 40.0),
                    hunger=r_dict.get("hunger", 100.0),
                    stamina=r_dict.get("stamina", 100.0),
                    injured=r_dict.get("injured", 0.0),
                    illness=r_dict.get("illness", 0.0),
                    distress=r_dict.get("distress", 0.0),
                    crying=bool(r_dict.get("crying", 0)),
                    credits=r_dict.get("credits", 10.0),
                    credit_score=r_dict.get("credit_score", 650.0),
                    breeding_cooldown=r_dict.get("breeding_cooldown", 0),
                    pregnant_ticks_remaining=r_dict.get("pregnant_ticks_remaining", 0),
                    pregnancy_father_id=r_dict.get("pregnancy_father_id"),
                    is_cross_species_pregnancy=bool(r_dict.get("is_cross_species_pregnancy", 0)),
                    last_prayer_tick=r_dict.get("last_prayer_tick", 0),
                    parent_ids=json.loads(r_dict.get("parent_ids_json") or "[]"),
                    spouse_id=r_dict.get("spouse_id"),
                    alive=bool(r_dict.get("alive", 1)),
                    quarantined=bool(r_dict.get("quarantined", 0)),
                    pos=pos_vec,
                    yaw=r_dict.get("yaw", 0.0),
                    traits=json.loads(r_dict.get("traits_json") or "{}"),
                    skills=json.loads(r_dict.get("skills_json") or "{}"),
                    tradition_ids=json.loads(r_dict.get("tradition_ids_json") or "[]"),
                    profession=r_dict.get("profession", "CITIZEN"),
                    profession_level=r_dict.get("profession_level", 1),
                    profession_xp=r_dict.get("profession_xp", 0.0),
                    hygiene=r_dict.get("hygiene", 1.0),
                    fatigue=r_dict.get("fatigue", 0.0),
                    known_books=json.loads(r_dict.get("known_books_json") or "[]"),
                    personality=personality_obj,
                    mood=mood_obj,
                    active_mechanical_effects=json.loads(
                        r_dict.get("active_mechanical_effects_json") or "{}"
                    ),
                    equipped_gear=json.loads(r_dict.get("equipped_gear_json") or "[]"),
                    home_building_id=r_dict.get("home_building_id"),
                )
                engine.agents[agent.agent_id] = agent
                engine.spatial_grid.update_agent(agent.agent_id, agent.pos.x, agent.pos.z)
                if agent.alive:
                    engine.judiciary.population_ledger["total_alive"] = (
                        engine.judiciary.population_ledger.get("total_alive", 0) + 1
                    )
                    engine.judiciary.population_ledger[agent.race] = (
                        engine.judiciary.population_ledger.get(agent.race, 0) + 1
                    )

                if agent.alive and hasattr(engine, "adapter") and engine.adapter:
                    engine.adapter.spawn_agent(
                        agent_id=agent.agent_id,
                        slot_idx=agent.slot_idx,
                        metadata=agent.model_dump(),
                    )

            # D. Rebuild patrol rosters: Palace Knights & City Guards
            if hasattr(engine, "palace_security") and engine.palace_security:
                engine.palace_security.rebuild_knight_roster(engine.agents)
            if hasattr(engine, "city_layout") and engine.city_layout:
                engine.city_layout.rebuild_guard_roster(engine.agents)

            # E. buildings
            cur.execute("SELECT * FROM buildings;")
            if hasattr(engine, "city_layout") and engine.city_layout:
                engine.city_layout.buildings.clear()
            if hasattr(engine, "housing_market") and engine.housing_market:
                engine.housing_market.frontier_buildings.clear()

            for r in cur.fetchall():
                r_dict = dict(r)
                bld = BuildingRecord(
                    building_id=r_dict["building_id"],
                    city_id=r_dict["city_id"],
                    building_type=cast(BuildingType, r_dict["building_type"]),
                    racial_style=cast(RacialStyle, r_dict["racial_style"]),
                    x=float(r_dict["x"]),
                    y=float(r_dict["y"]),
                    z=float(r_dict["z"]),
                    rotation_y=float(r_dict.get("rotation_y", 0.0)),
                    parcel_x=int(r_dict["parcel_x"]),
                    parcel_z=int(r_dict["parcel_z"]),
                    footprint_radius=float(r_dict.get("footprint_radius", 8.0)),
                    owner_id=r_dict.get("owner_id"),
                    owner_name=r_dict.get("owner_name"),
                    for_sale=bool(r_dict.get("for_sale", 0)),
                    sale_price=float(r_dict.get("sale_price", 0.0)),
                    settlement_id=r_dict.get("settlement_id"),
                    is_frontier=bool(r_dict.get("is_frontier", 0)),
                )
                if bld.is_frontier and hasattr(engine, "housing_market") and engine.housing_market:
                    engine.housing_market.frontier_buildings[bld.building_id] = bld
                if hasattr(engine, "city_layout") and engine.city_layout:
                    engine.city_layout.buildings[bld.building_id] = bld
                if hasattr(engine, "navigation") and engine.navigation:
                    engine.navigation.register_building_footprint(
                        name=bld.building_id,
                        cx=bld.x,
                        cz=bld.z,
                        radius=bld.footprint_radius,
                        door_x=bld.x,
                        door_z=bld.z + bld.footprint_radius,
                        building_type=bld.building_type,
                    )
            if hasattr(engine, "housing_market") and engine.housing_market:
                engine.housing_market.pioneer_count = len(engine.housing_market.frontier_buildings)

            # F. parcels
            cur.execute("SELECT * FROM parcels;")
            engine.property_mgr.parcels.clear()
            for r in cur.fetchall():
                r_dict = dict(r)
                p = ParcelRecord(
                    parcel_id=r_dict["parcel_id"],
                    cx=int(r_dict["cx"]),
                    cz=int(r_dict["cz"]),
                    settlement_id=r_dict.get("settlement_id"),
                    nation_id=r_dict.get("nation_id"),
                    owner_id=r_dict.get("owner_id"),
                    owner_type=r_dict.get("owner_type", "UNCLAIMED"),
                    has_altar=bool(r_dict.get("has_altar", 0)),
                    has_library=bool(r_dict.get("has_library", 0)),
                    assessed_value=float(r_dict.get("assessed_value", 100.0)),
                    for_sale_price=(
                        float(r_dict["for_sale_price"])
                        if r_dict.get("for_sale_price") is not None
                        else None
                    ),
                    tenant_id=r_dict.get("tenant_id"),
                    rent_per_civic_tick=float(r_dict.get("rent_per_civic_tick", 0.0)),
                    updated_tick=int(r_dict.get("updated_tick", 0)),
                )
                engine.property_mgr.parcels[p.parcel_id] = p
                if p.settlement_id:
                    engine.border_mgr.register_settlement_border(p.settlement_id, [p.parcel_id])

            # G. settlements
            cur.execute("SELECT * FROM settlements;")
            if hasattr(engine, "political_engine") and engine.political_engine:
                engine.political_engine.polities.clear()
            if hasattr(engine, "housing_market") and engine.housing_market:
                engine.housing_market.frontier_villages.clear()

            for r in cur.fetchall():
                r_dict = dict(r)
                center_pos_dict = json.loads(r_dict.get("center_pos_json") or "{}")
                c_pos = Vec3(**center_pos_dict) if center_pos_dict else Vec3(x=0.0, y=0.0, z=0.0)
                border_ids = json.loads(r_dict.get("border_parcel_ids_json") or "[]")

                polity = Polity(
                    settlement_id=r_dict["settlement_id"],
                    name=r_dict["name"],
                    tier=cast(SettlementTier, r_dict["tier"]),
                    regime_type=r_dict.get("regime_type", "CHIEFDOM"),
                    leader_id=r_dict.get("leader_id"),
                    treasury_credits=float(r_dict.get("treasury_credits", 100.0)),
                    tax_rate=float(r_dict.get("tax_rate", 0.05)),
                    tariff_rate=float(r_dict.get("tariff_rate", 0.0)),
                    is_neutral_free_city=bool(r_dict.get("is_neutral_free_city", 0)),
                    war_exempt=bool(r_dict.get("war_exempt", 0)),
                )
                polity.border_parcels = set(border_ids)
                polity.at_war_with = set(json.loads(r_dict.get("at_war_with_json") or "[]"))
                polity.allied_with = set(json.loads(r_dict.get("allied_with_json") or "[]"))

                if hasattr(engine, "political_engine") and engine.political_engine:
                    engine.political_engine.polities[polity.settlement_id] = polity

                if (
                    polity.tier == "VILLAGE"
                    and hasattr(engine, "housing_market")
                    and engine.housing_market
                ):
                    village = SettlementRecord(
                        settlement_id=r_dict["settlement_id"],
                        name=r_dict["name"],
                        tier="VILLAGE",
                        parent_polity_id=r_dict.get("parent_polity_id"),
                        regime_type=r_dict.get("regime_type", "CHIEFDOM"),
                        is_holy_polity=bool(r_dict.get("is_holy_polity", 0)),
                        is_neutral_free_city=bool(r_dict.get("is_neutral_free_city", 0)),
                        war_exempt=bool(r_dict.get("war_exempt", 0)),
                        state_religion_id=r_dict.get("state_religion_id"),
                        founder_id=r_dict.get("founder_id", "system"),
                        leader_id=r_dict.get("leader_id"),
                        center_pos=c_pos,
                        border_parcel_ids=border_ids,
                        treasury_credits=float(r_dict.get("treasury_credits", 100.0)),
                        tax_rate=float(r_dict.get("tax_rate", 0.05)),
                        tariff_rate=float(r_dict.get("tariff_rate", 0.0)),
                        next_election_tick=(
                            int(r_dict["next_election_tick"])
                            if r_dict.get("next_election_tick") is not None
                            else None
                        ),
                        laws=json.loads(r_dict.get("laws_json") or "[]"),
                        at_war_with=list(polity.at_war_with),
                        allied_with=list(polity.allied_with),
                        founded_tick=int(r_dict.get("founded_tick", 0)),
                    )
                    engine.housing_market.frontier_villages[village.settlement_id] = village

            # H. religions
            cur.execute("SELECT * FROM religions;")
            engine.religion_mgr.religions.clear()
            for r in cur.fetchall():
                r_dict = dict(r)
                rel = ReligionRecord(
                    religion_id=r_dict["religion_id"],
                    name=r_dict["name"],
                    aligned_deity_slot=cast(DeitySlot, r_dict["aligned_deity_slot"]),
                    founder_id=r_dict["founder_id"],
                    pope_id=r_dict.get("pope_id"),
                    treasury_credits=float(r_dict.get("treasury_credits", 0.0)),
                    tenets=json.loads(r_dict.get("tenets_json") or "{}"),
                    canonized_entry_ids=json.loads(
                        r_dict.get("canonized_entry_ids_json") or "[]"
                    ),
                    excommunicated_ids=json.loads(
                        r_dict.get("excommunicated_ids_json") or "[]"
                    ),
                    founded_tick=int(r_dict.get("founded_tick", 0)),
                )
                engine.religion_mgr.religions[rel.religion_id] = rel

            # I. judiciary_cases & criminal_records
            cur.execute("SELECT * FROM judiciary_cases;")
            engine.judiciary.cases.clear()
            for r in cur.fetchall():
                r_dict = dict(r)
                case = JudiciaryCaseRecord(
                    case_id=r_dict["case_id"],
                    settlement_id=r_dict["settlement_id"],
                    accused_id=r_dict["accused_id"],
                    victim_id=r_dict.get("victim_id"),
                    offense_type=r_dict["offense_type"],
                    combat_context=r_dict.get("combat_context"),
                    witness_ids=json.loads(r_dict.get("witness_ids_json") or "[]"),
                    evidence_score=float(r_dict["evidence_score"]),
                    status=r_dict["status"],
                    ruling=r_dict.get("ruling"),
                    penalty_credits=float(r_dict.get("penalty_credits", 0.0)),
                    opened_tick=int(r_dict["opened_tick"]),
                    closed_tick=(
                        int(r_dict["closed_tick"])
                        if r_dict.get("closed_tick") is not None
                        else None
                    ),
                )
                engine.judiciary.cases[case.case_id] = case

            # Restore criminal records from table, falling back to non-acquitted cases
            engine.judiciary.criminal_records.clear()
            try:
                cur.execute("SELECT agent_id, case_id FROM criminal_records;")
                for r in cur.fetchall():
                    ag_id, c_id = r["agent_id"], r["case_id"]
                    engine.judiciary.criminal_records.setdefault(ag_id, []).append(c_id)
            except sqlite3.OperationalError:
                pass

            if not engine.judiciary.criminal_records:
                for c in engine.judiciary.cases.values():
                    if c.status == "CLOSED" and c.ruling != "ACQUITTED":
                        engine.judiciary.criminal_records.setdefault(
                            c.accused_id, []
                        ).append(c.case_id)

            # J. fatalities
            cur.execute("SELECT * FROM fatalities;")
            engine.judiciary.fatality_index.clear()
            for r in cur.fetchall():
                r_dict = dict(r)
                fatality = FatalityRecord(
                    agent_id=r_dict["agent_id"],
                    display_name=r_dict["display_name"],
                    race=r_dict["race"],
                    sub_lineage=r_dict.get("sub_lineage"),
                    secondary_heritage_race=r_dict.get("secondary_heritage_race"),
                    age_ticks=int(r_dict["age_ticks"]),
                    stage_at_death=r_dict["stage_at_death"],
                    cause=r_dict["cause"],
                    combat_context=r_dict.get("combat_context"),
                    killer_id=r_dict.get("killer_id"),
                    settlement_id=r_dict.get("settlement_id"),
                    season=r_dict["season"],
                    death_day=int(r_dict["death_day"]),
                    death_tick=int(r_dict["death_tick"]),
                )
                engine.judiciary.fatality_index.append(fatality)

            # K. world_library
            cur.execute("SELECT * FROM world_library;")
            engine.governance_engine.library_entries.clear()
            for r in cur.fetchall():
                r_dict = dict(r)
                book = WorldLibraryEntry(
                    entry_id=r_dict["entry_id"],
                    topic=r_dict["topic"],
                    title=r_dict["title"],
                    summary=r_dict["summary"],
                    author_id=r_dict["author_id"],
                    author_proficiency=float(r_dict.get("author_proficiency", 1.0)),
                    skill_bonus=float(r_dict.get("skill_bonus", 0.08)),
                    is_scripture=bool(r_dict.get("is_scripture", 0)),
                    read_count=int(r_dict.get("read_count", 0)),
                    created_tick=int(r_dict["created_tick"]),
                    subject=r_dict.get("subject"),
                    section=r_dict.get("section"),
                    fact_key=r_dict.get("fact_key"),
                    tags=json.loads(r_dict.get("tags_json") or "[]"),
                    mechanical_effects=json.loads(r_dict.get("mechanical_effects_json") or "{}"),
                    author_type=r_dict.get("author_type", "MORTAL"),
                    body=r_dict.get("body"),
                )
                engine.governance_engine.library_entries[book.entry_id] = book

            # L. divine_codex
            cur.execute("SELECT * FROM divine_codex;")
            engine.governance_engine.codex_entries.clear()
            for r in cur.fetchall():
                r_dict = dict(r)
                decree = DivineCodexEntry(
                    entry_id=r_dict["entry_id"],
                    title=r_dict["title"],
                    text=r_dict["text"],
                    category=r_dict["category"],
                    parameter_key=r_dict.get("parameter_key"),
                    parameter_value_json=r_dict.get("parameter_value_json"),
                    author_slot=r_dict["author_slot"],
                    supporting_daughter_slots=json.loads(
                        r_dict.get("supporting_daughter_slots_json") or "[]"
                    ),
                    approved_by_god=bool(r_dict.get("approved_by_god", 0)),
                    created_tick=int(r_dict["created_tick"]),
                )
                engine.governance_engine.codex_entries[decree.entry_id] = decree

            # M. divine_codex_proposals
            cur.execute("SELECT * FROM divine_codex_proposals;")
            engine.governance_engine.codex_proposals.clear()
            for r in cur.fetchall():
                r_dict = dict(r)
                prop = DivineCodexProposalRecord(
                    proposal_id=r_dict["proposal_id"],
                    title=r_dict["title"],
                    text=r_dict["text"],
                    parameter_key=r_dict["parameter_key"],
                    parameter_value_json=r_dict["parameter_value_json"],
                    proposer_slot=cast(DeitySlot, r_dict["proposer_slot"]),
                    co_sponsors=json.loads(r_dict.get("co_sponsors_json") or "[]"),
                    status=r_dict.get("status", "PENDING_GOD"),
                    submitted_tick=int(r_dict["submitted_tick"]),
                    resolved_tick=(
                        int(r_dict["resolved_tick"])
                        if r_dict.get("resolved_tick") is not None
                        else None
                    ),
                )
                engine.governance_engine.codex_proposals[prop.proposal_id] = prop
