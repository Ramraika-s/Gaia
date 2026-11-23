"""
sim_core/society/judiciary.py
Context-aware Judiciary adjudicating offenses, evidence, and rulings.
Enforces automatic acquittal for SELF_DEFENSE, DEFENDING_KIN_OR_TOWN, and ACTIVE_WAR.
Maintains Population Ledger, Fatality Index, and Criminal Records.
Follows SOCIETY_AND_GOVERNANCE_SPEC.md Section 6.2.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from sim_core.schemas import (
    CombatContext,
    DeathCause,
    FatalityRecord,
    JudiciaryCaseRecord,
    Season,
)

AUTO_ACQUITTED_CONTEXTS: set[CombatContext] = {
    "SELF_DEFENSE",
    "DEFENDING_KIN_OR_TOWN",
    "ACTIVE_WAR",
}


class JudiciaryEngine:
    """
    Context-aware Judiciary and Vital Statistics registry:
    - Adjudicates cases with evidence evaluation.
    - Verified self-defense / active war are immediately acquitted with 0 criminal record.
    - Maintains population, fatality, and criminal indices.
    """

    def __init__(self):
        self.cases: dict[str, JudiciaryCaseRecord] = {}
        self.criminal_records: dict[str, list[str]] = {}  # agent_id -> list of case_ids
        self.fatalities: list[FatalityRecord] = []
        self.population_ledger: dict[str, int] = {
            "total_alive": 0,
            "HUMAN": 0,
            "ELF": 0,
            "DRAGON": 0,
            "BEASTHUMAN": 0,
        }

    @property
    def fatality_index(self) -> list[FatalityRecord]:
        return self.fatalities

    # =========================================================================
    # 1. Case Management & Adjudication
    # =========================================================================

    def file_case(
        self,
        accused_id: str,
        offense_type: Literal[
            "THEFT",
            "UNPROVOKED_ATTACK",
            "VANDALISM",
            "DEBT_DEFAULT",
            "TRESPASS",
            "CONTESTED_COMBAT",
        ],
        opened_tick: int,
        settlement_id: str | None = None,
        victim_id: str | None = None,
        combat_context: CombatContext | None = None,
        witness_ids: list[str] | None = None,
        evidence_score: float = 0.0,
    ) -> JudiciaryCaseRecord:
        """
        Files a new judiciary case.
        If offense involves combat and has verified self-defense, kin defense,
        or active war context, it is automatically ACQUITTED immediately.
        """
        case_id = f"case_{uuid.uuid4().hex[:12]}"
        witnesses = witness_ids or []
        evidence = max(0.0, min(1.0, evidence_score))

        # Check for auto-acquittal under combat context
        if combat_context in AUTO_ACQUITTED_CONTEXTS:
            case = JudiciaryCaseRecord(
                case_id=case_id,
                settlement_id=settlement_id,
                accused_id=accused_id,
                victim_id=victim_id,
                offense_type=offense_type,
                combat_context=combat_context,
                witness_ids=witnesses,
                evidence_score=evidence,
                status="CLOSED",
                ruling="ACQUITTED",
                penalty_credits=0.0,
                opened_tick=opened_tick,
                closed_tick=opened_tick,
            )
            self.cases[case_id] = case
            return case

        case = JudiciaryCaseRecord(
            case_id=case_id,
            settlement_id=settlement_id,
            accused_id=accused_id,
            victim_id=victim_id,
            offense_type=offense_type,
            combat_context=combat_context,
            witness_ids=witnesses,
            evidence_score=evidence,
            status="OPEN",
            ruling=None,
            penalty_credits=0.0,
            opened_tick=opened_tick,
            closed_tick=None,
        )
        self.cases[case_id] = case
        return case

    def adjudicate_case(
        self,
        case_id: str,
        closed_tick: int,
        ruling: Literal["ACQUITTED", "RESTITUTION", "FINE", "GARNISH", "BANISHMENT"],
        penalty_credits: float = 0.0,
    ) -> tuple[bool, str, JudiciaryCaseRecord | None]:
        """
        Issues a ruling on an open case.
        Non-acquitted rulings update the domestic criminal record.
        """
        case = self.cases.get(case_id)
        if not case:
            return False, "CASE_NOT_FOUND", None
        if case.status == "CLOSED":
            return False, "CASE_ALREADY_CLOSED", case

        case.status = "CLOSED"
        case.ruling = ruling
        case.closed_tick = closed_tick
        case.penalty_credits = max(0.0, penalty_credits)

        if ruling != "ACQUITTED":
            if case.accused_id not in self.criminal_records:
                self.criminal_records[case.accused_id] = []
            self.criminal_records[case.accused_id].append(case_id)

        return True, f"RULING_{ruling}_RECORDED", case

    def get_criminal_record(self, agent_id: str) -> list[JudiciaryCaseRecord]:
        """Returns all convicting cases for an agent."""
        case_ids = self.criminal_records.get(agent_id, [])
        return [self.cases[cid] for cid in case_ids if cid in self.cases]

    def get_open_cases(self, settlement_id: str | None = None) -> list[JudiciaryCaseRecord]:
        """Returns all unresolved cases, optionally filtered by settlement."""
        open_cases = [c for c in self.cases.values() if c.status == "OPEN"]
        if settlement_id is not None:
            open_cases = [c for c in open_cases if c.settlement_id == settlement_id]
        return open_cases

    # =========================================================================
    # 2. Vital Statistics & Fatality Index
    # =========================================================================

    def record_fatality(
        self,
        record: FatalityRecord | None = None,
        *,
        agent: Any = None,
        day: int = 1,
        season: Season = "SPRING",
        cause: DeathCause = "HAZARD",
        killer_id: str | None = None,
        combat_context: CombatContext | None = None,
        death_tick: int = 0,
    ) -> FatalityRecord:
        """Records a mortal death and decrements alive counters."""
        if record is None:
            if agent is None:
                raise ValueError("Must provide either a FatalityRecord or an agent instance.")
            record = FatalityRecord(
                agent_id=agent.agent_id,
                display_name=agent.display_name,
                race=agent.race,
                sub_lineage=getattr(agent, "sub_lineage", None),
                secondary_heritage_race=getattr(agent, "secondary_heritage_race", None),
                age_ticks=getattr(agent, "age_ticks", 0),
                stage_at_death=getattr(agent, "stage", "ADULT"),
                cause=cause,
                combat_context=combat_context,
                killer_id=killer_id,
                settlement_id=getattr(agent, "settlement_id", None),
                season=season,
                death_day=day,
                death_tick=death_tick,
            )

        self.fatalities.append(record)
        if self.population_ledger["total_alive"] > 0:
            self.population_ledger["total_alive"] -= 1
        race_key = str(record.race)
        if race_key in self.population_ledger and self.population_ledger[race_key] > 0:
            self.population_ledger[race_key] -= 1
        return record

    def update_population_counts(self, counts: dict[str, int]) -> None:
        """Refreshes population stats."""
        self.population_ledger.update(counts)

    def get_fatality_stats(self) -> dict[str, Any]:
        """Calculates aggregated fatality analytics."""
        by_cause: dict[str, int] = {}
        by_race: dict[str, int] = {}
        by_season: dict[str, int] = {}
        infant_mortality = 0
        birth_complications = 0

        for f in self.fatalities:
            by_cause[f.cause] = by_cause.get(f.cause, 0) + 1
            by_race[f.race] = by_race.get(f.race, 0) + 1
            by_season[f.season] = by_season.get(f.season, 0) + 1

            if f.stage_at_death == "INFANT":
                infant_mortality += 1
            if f.cause == "BIRTH_COMPLICATION":
                birth_complications += 1

        return {
            "total_fatalities": len(self.fatalities),
            "infant_mortality": infant_mortality,
            "birth_complications": birth_complications,
            "by_cause": by_cause,
            "by_race": by_race,
            "by_season": by_season,
        }
