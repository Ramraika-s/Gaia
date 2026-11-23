"""
sim_core/society/library.py
Two-Book Governance: World Library (world_library) mortal/divine scholarship,
and Divine Rules Book (divine_codex) decrees and engine-parameter overrides.
Follows Two-Book Governance Option B Split Write Authority specification.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any, Literal

from sim_core.config import TICKS_PER_GAME_DAY
from sim_core.knowledge.schema import KnowledgeEntry
from sim_core.schemas import (
    DeitySlot,
    DivineCodexEntry,
    DivineCodexProposalRecord,
    LibraryProposalRecord,
    WorldLibraryEntry,
)

OBJECTION_WINDOW_TICKS = TICKS_PER_GAME_DAY  # 1 game day
EXPIRY_TICKS = 30 * TICKS_PER_GAME_DAY  # 30 game days


class TwoBookGovernanceEngine:
    """
    Manages both World Library and Divine Codex with strict RBAC:
    - world_library: readable by everyone; edited by God, Goddess+1 Daughter,
      3/4 Daughters alone, or mortals passing Elders (>50%) and God-Mothers review.
    - divine_codex: readable by everyone; Option B split authority where only God
      can write/apply engine parameter overrides (proposed by Goddess or 4/4 Daughters).
    """

    def __init__(self):
        # World Library storage
        self.library_entries: dict[str, WorldLibraryEntry | KnowledgeEntry] = {}
        self.library_proposals: dict[str, LibraryProposalRecord] = {}

        # Divine Codex storage
        self.codex_entries: dict[str, DivineCodexEntry] = {}
        self.codex_proposals: dict[str, DivineCodexProposalRecord] = {}

        # Live engine parameter overrides applied via Divine Codex
        self.live_engine_overrides: dict[str, Any] = {}

    # =========================================================================
    # 1. World Library Governance (world_library)
    # =========================================================================

    def write_library_direct_god(
        self,
        entry: WorldLibraryEntry,
    ) -> tuple[bool, str]:
        """God (Admin) direct write to World Library anytime."""
        self.library_entries[entry.entry_id] = entry
        return True, "GOD_LIBRARY_ENTRY_COMMITTED"

    def write_library_goddess_with_daughters(
        self,
        entry: WorldLibraryEntry,
        daughter_approvals: list[DeitySlot],
    ) -> tuple[bool, str]:
        """World Goddess may edit directly with at least 1 Daughter approval."""
        if len(daughter_approvals) < 1:
            return False, "REJECTED: World Goddess requires >= 1 Daughter approval"

        self.library_entries[entry.entry_id] = entry
        return True, "GODDESS_LIBRARY_ENTRY_COMMITTED"

    def write_library_daughters_alone(
        self,
        entry: WorldLibraryEntry,
        daughter_approvals: list[DeitySlot],
    ) -> tuple[bool, str]:
        """5 Daughters alone may edit if > 50% (at least 3 of 5) approve."""
        valid_daughters = {"gm_human", "gm_elf", "gm_dragon", "gm_beasthuman", "gm_demon"}
        unique_approvals = {d for d in daughter_approvals if d in valid_daughters}

        if len(unique_approvals) < 3:
            return False, (
                f"REJECTED: Daughters alone require >= 3 approvals, got {len(unique_approvals)}"
            )

        self.library_entries[entry.entry_id] = entry
        return True, "DAUGHTERS_COUNCIL_LIBRARY_ENTRY_COMMITTED"

    def draft_mortal_proposal(
        self,
        author_id: str,
        topic: str,
        title: str,
        summary: str,
        author_proficiency: float,
        current_tick: int,
        action: Literal["CREATE", "EDIT", "SUPERSEDE"] = "CREATE",
        target_entry_id: str | None = None,
        is_scripture: bool = False,
        body: str | None = None,
        subject: str | None = None,
        section: str | None = None,
        fact_key: str | None = None,
        tags: list[str] | None = None,
        mechanical_effects: dict[str, float] | None = None,
        author_type: Literal["DIVINE", "MORTAL", "SYSTEM", "UNKNOWN"] = "MORTAL",
        supersedes: list[str] | None = None,
        distinct_from: list[str] | None = None,
    ) -> tuple[bool, str, LibraryProposalRecord | None]:
        """Mortal drafts a World Library change proposal."""
        if not is_scripture and author_proficiency < 0.70:
            return False, f"REJECTED: author proficiency {author_proficiency:.2f} < 0.70", None

        proposal_id = f"lib_prop_{uuid.uuid4().hex[:8]}"
        proposal = LibraryProposalRecord(
            proposal_id=proposal_id,
            action=action,
            target_entry_id=target_entry_id,
            author_id=author_id,
            topic=topic,
            title=title,
            summary=summary,
            author_proficiency=author_proficiency,
            votes_approve=[],
            votes_reject=[],
            godmother_approvals=[],
            godmother_objections=[],
            first_approval_tick=None,
            status="OPEN",
            created_tick=current_tick,
            body=body or summary,
            subject=subject,
            section=section,
            fact_key=fact_key,
            tags=tags or [],
            mechanical_effects=mechanical_effects or {},
            author_type=author_type,
            supersedes=supersedes or [],
            distinct_from=distinct_from or [],
        )
        self.library_proposals[proposal_id] = proposal
        return True, "PROPOSAL_DRAFTED", proposal

    def submit_mortal_book_petition(
        self,
        author_id: str,
        subject: str,
        topic: str,
        title: str,
        summary: str,
        body: str = "",
        target_section: str = "general",
        fact_key: str | None = None,
        tags: list[str] | None = None,
        mechanical_effects: dict[str, float] | None = None,
        author_proficiency: float = 0.80,
        current_tick: int = 0,
        supersedes: list[str] | None = None,
        distinct_from: list[str] | None = None,
    ) -> tuple[bool, str, LibraryProposalRecord | None]:
        """
        Submits a mortal book petition through 3-Stage deduplication check first.
        Rejects duplicate petitions automatically before wasting Elder/Daughter votes.
        Routes valid novel entries to OPEN proposal status for the governance pipeline.
        """
        from sim_core.knowledge.dedupe import audit_single_entry

        if not fact_key:
            clean_sub = re.sub(r"[^a-z0-9_]+", "_", subject.lower()).strip("_")
            clean_top = re.sub(r"[^a-z0-9_]+", "_", topic.lower()).strip("_")
            clean_tit = re.sub(r"[^a-z0-9_]+", "_", title.lower()).strip("_")
            fact_key = f"{clean_sub or 'general'}.{clean_top or 'topic'}.{clean_tit or 'concept'}"

        entry_id = f"mortal_{author_id}_{uuid.uuid4().hex[:6]}"
        entry_dict = {
            "entry_id": entry_id,
            "subject": subject,
            "target_section": target_section,
            "fact_key": fact_key,
            "title": title,
            "summary": summary,
            "body": body or summary,
            "author": author_id,
            "author_type": "MORTAL",
            "era_tier": 1,
            "tags": tags or ["mortal_petition"],
            "prerequisites": [],
            "mechanical_effects": mechanical_effects or {},
            "supersedes": supersedes or [],
            "distinct_from": distinct_from or [],
        }

        # 3-Stage Deduplication against existing World Library entries
        is_valid, reason, _ = audit_single_entry(entry_dict, list(self.library_entries.values()))
        if not is_valid:
            return False, f"REJECTED_DUPLICATE: {reason}", None

        # Novel entry -> draft proposal
        ok, msg, prop = self.draft_mortal_proposal(
            author_id=author_id,
            topic=topic,
            title=title,
            summary=summary,
            author_proficiency=author_proficiency,
            current_tick=current_tick,
            action="CREATE",
            body=body or summary,
            subject=subject,
            section=target_section,
            fact_key=fact_key,
            tags=tags or ["mortal_petition"],
            mechanical_effects=mechanical_effects or {},
            author_type="MORTAL",
            supersedes=supersedes or [],
            distinct_from=distinct_from or [],
        )
        if not ok:
            return False, msg, None

        return True, "PETITION_ACCEPTED_FOR_VOTING", prop

    def _commit_entry_from_proposal(
        self,
        prop: LibraryProposalRecord,
        current_tick: int,
    ) -> WorldLibraryEntry:
        """Commits approved proposal to World Library in RAM and exports mortal book."""
        entry_id = prop.target_entry_id or f"entry_{uuid.uuid4().hex[:8]}"
        entry = WorldLibraryEntry(
            entry_id=entry_id,
            topic=prop.topic,
            title=prop.title,
            summary=prop.summary,
            author_id=prop.author_id,
            author_proficiency=prop.author_proficiency,
            created_tick=current_tick,
            body=prop.body or prop.summary,
            subject=prop.subject or prop.topic,
            section=prop.section or "general",
            fact_key=prop.fact_key or f"{prop.subject or 'general'}.topic.{entry_id}",
            tags=prop.tags,
            mechanical_effects=prop.mechanical_effects,
            author_type=prop.author_type,
            supersedes=prop.supersedes,
            distinct_from=prop.distinct_from,
        )
        self.library_entries[entry_id] = entry
        self._export_mortal_authored_entry(entry)
        return entry

    def _export_mortal_authored_entry(self, entry: WorldLibraryEntry) -> None:
        """Exports approved mortal-authored books to data/knowledge/_mortal_authored/."""
        if entry.author_type != "MORTAL":
            return
        mortal_dir = Path("data/knowledge/_mortal_authored")
        mortal_dir.mkdir(parents=True, exist_ok=True)
        filename = f"scribe_{entry.author_id}_{entry.entry_id}.json"
        pack_data = {
            "pack_id": f"mortal_pack_{entry.entry_id}",
            "entries": [
                {
                    "entry_id": entry.entry_id,
                    "subject": entry.subject or "law_and_governance",
                    "target_section": entry.section or "general",
                    "fact_key": (
                        entry.fact_key
                        or f"{entry.subject or 'law_and_governance'}.topic.{entry.entry_id}"
                    ),
                    "title": entry.title,
                    "summary": entry.summary,
                    "body": entry.body or entry.summary,
                    "author": entry.author_id,
                    "author_type": "MORTAL",
                    "era_tier": 1,
                    "tags": entry.tags or ["mortal_petition"],
                    "prerequisites": [],
                    "mechanical_effects": entry.mechanical_effects,
                    "supersedes": entry.supersedes,
                    "distinct_from": entry.distinct_from,
                }
            ],
        }
        with open(mortal_dir / filename, "w", encoding="utf-8") as f:
            json.dump(pack_data, f, indent=2)

    def cast_elder_vote(
        self,
        proposal_id: str,
        elder_id: str,
        vote: Literal["APPROVE", "REJECT"],
        total_appointed_elders: int,
    ) -> tuple[bool, str]:
        """Appointed Council Elder casts vote on proposal."""
        if proposal_id not in self.library_proposals:
            return False, "PROPOSAL_NOT_FOUND"

        prop = self.library_proposals[proposal_id]
        if prop.status != "OPEN":
            return False, f"VOTING_CLOSED: status is {prop.status}"

        if elder_id in prop.votes_approve or elder_id in prop.votes_reject:
            return False, "DUPLICATE_VOTE"

        if vote == "APPROVE":
            prop.votes_approve.append(elder_id)
        else:
            prop.votes_reject.append(elder_id)

        # Check if Elder consensus (> 50%) passed
        if total_appointed_elders > 0 and len(prop.votes_approve) * 2 > total_appointed_elders:
            prop.status = "PENDING_GODMOTHERS"
            return True, "PASSED_ELDERS_PENDING_GODMOTHERS"

        return True, "ELDER_VOTE_RECORDED"

    def cast_godmother_vote(
        self,
        proposal_id: str,
        godmother_slot: DeitySlot,
        vote: Literal["APPROVE", "OBJECT"],
        current_tick: int,
    ) -> tuple[bool, str]:
        """
        Racial God-Mother evaluates a proposal that passed the Elders Council:
        - 0 approvals in 30 days -> auto-expires
        - >= 1 approval -> starts 1-game-day objection window
        - >= 3/4 objections before window ends -> BLOCKED_BY_DAUGHTERS
        - < 3 objections when window elapses -> APPROVED
        """
        if proposal_id not in self.library_proposals:
            return False, "PROPOSAL_NOT_FOUND"

        prop = self.library_proposals[proposal_id]
        if prop.status not in ("PENDING_GODMOTHERS", "OBJECTION_WINDOW"):
            return False, f"INVALID_STATUS_FOR_GODMOTHER_VOTE: {prop.status}"

        valid_daughters = {"gm_human", "gm_elf", "gm_dragon", "gm_beasthuman", "gm_demon"}
        if godmother_slot not in valid_daughters:
            return False, f"INVALID_GODMOTHER_SLOT: {godmother_slot}"

        if (
            godmother_slot in prop.godmother_approvals
            or godmother_slot in prop.godmother_objections
        ):
            return False, "DUPLICATE_GODMOTHER_VOTE"

        if vote == "APPROVE":
            prop.godmother_approvals.append(godmother_slot)
            if prop.first_approval_tick is None:
                prop.first_approval_tick = current_tick
                prop.status = "OBJECTION_WINDOW"
        else:
            prop.godmother_objections.append(godmother_slot)
            # Check if >= 3/4 Daughters objected (>50% objections)
            if len(prop.godmother_objections) >= 3:
                prop.status = "BLOCKED_BY_DAUGHTERS"
                return True, "BLOCKED_BY_DAUGHTERS"

        return True, f"GODMOTHER_{vote}_RECORDED"

    def advance_proposal_lifecycle(
        self,
        proposal_id: str,
        current_tick: int,
    ) -> str:
        """Checks 30-day expiry and 1-day objection window expiration."""
        if proposal_id not in self.library_proposals:
            return "PROPOSAL_NOT_FOUND"

        prop = self.library_proposals[proposal_id]

        # 30-day expiry check if 0 God-Mothers approve
        if prop.status == "PENDING_GODMOTHERS":
            if current_tick - prop.created_tick >= EXPIRY_TICKS:
                prop.status = "EXPIRED"
                return "EXPIRED"

        # 1-day objection window elapsing check
        if prop.status == "OBJECTION_WINDOW" and prop.first_approval_tick is not None:
            if current_tick - prop.first_approval_tick >= OBJECTION_WINDOW_TICKS:
                if len(prop.godmother_objections) >= 3:
                    prop.status = "BLOCKED_BY_DAUGHTERS"
                    return "BLOCKED_BY_DAUGHTERS"
                else:
                    prop.status = "APPROVED"
                    # Commit to World Library
                    self._commit_entry_from_proposal(prop, current_tick)
                    return "APPROVED_AND_COMMITTED"

        return prop.status

    def appeal_blocked_proposal(
        self,
        proposal_id: str,
        appeal_target: Literal["WORLD_GODDESS", "GOD"],
    ) -> tuple[bool, str]:
        """Submits an appeal for a proposal blocked by Daughters."""
        if proposal_id not in self.library_proposals:
            return False, "PROPOSAL_NOT_FOUND"

        prop = self.library_proposals[proposal_id]
        if prop.status != "BLOCKED_BY_DAUGHTERS":
            return False, f"INVALID_STATUS_FOR_APPEAL: {prop.status}"

        prop.appeal_target = appeal_target
        return True, f"APPEAL_SUBMITTED_TO_{appeal_target}"

    def resolve_appeal_world_goddess(
        self,
        proposal_id: str,
        approved: bool,
        current_tick: int,
    ) -> tuple[bool, str]:
        """World Goddess adjudicates a blocked mortal proposal appeal."""
        if proposal_id not in self.library_proposals:
            return False, "PROPOSAL_NOT_FOUND"

        prop = self.library_proposals[proposal_id]
        if prop.appeal_target != "WORLD_GODDESS":
            return False, f"WRONG_APPEAL_TARGET: {prop.appeal_target}"

        if approved:
            prop.status = "APPROVED"
            prop.appeal_ruling = "UPHELD"
            self._commit_entry_from_proposal(prop, current_tick)
            return True, "APPEAL_UPHELD_AND_COMMITTED"
        else:
            prop.status = "REJECTED"
            prop.appeal_ruling = "REJECTED"
            return True, "APPEAL_REJECTED"

    def resolve_appeal_god(
        self,
        proposal_id: str,
        approved: bool,
        current_tick: int,
    ) -> tuple[bool, str]:
        """God adjudicates a blocked mortal proposal appeal."""
        if proposal_id not in self.library_proposals:
            return False, "PROPOSAL_NOT_FOUND"

        prop = self.library_proposals[proposal_id]
        if prop.appeal_target != "GOD":
            return False, f"WRONG_APPEAL_TARGET: {prop.appeal_target}"

        if approved:
            prop.status = "APPROVED"
            prop.appeal_ruling = "UPHELD"
            self._commit_entry_from_proposal(prop, current_tick)
            return True, "GOD_APPEAL_UPHELD_AND_COMMITTED"
        else:
            prop.status = "REJECTED"
            prop.appeal_ruling = "REJECTED"
            return True, "GOD_APPEAL_REJECTED"

    # =========================================================================
    # 2. Divine Rules Book Governance (divine_codex) — Option B
    # =========================================================================

    def write_codex_direct_god(
        self,
        title: str,
        text: str,
        category: Literal["DECREE", "COVENANT_LAW", "WAR_DIRECTIVE", "PARAMETER_OVERRIDE"],
        current_tick: int,
        parameter_key: str | None = None,
        parameter_value: Any | None = None,
    ) -> tuple[bool, str, DivineCodexEntry]:
        """God (Admin) direct write of text decree or engine parameter override."""
        entry_id = f"codex_{uuid.uuid4().hex[:8]}"
        param_val_json = json.dumps(parameter_value) if parameter_value is not None else None

        entry = DivineCodexEntry(
            entry_id=entry_id,
            title=title,
            text=text,
            category=category,
            parameter_key=parameter_key,
            parameter_value_json=param_val_json,
            author_slot="GOD",
            supporting_daughter_slots=[],
            approved_by_god=True,
            created_tick=current_tick,
        )
        self.codex_entries[entry_id] = entry

        # If parameter override, apply immediately to live engine
        if parameter_key is not None and parameter_value is not None:
            self.live_engine_overrides[parameter_key] = parameter_value

        return True, "GOD_CODEX_ENTRY_COMMITTED", entry

    def write_codex_text_decree_goddess_and_daughters(
        self,
        title: str,
        text: str,
        daughter_approvals: list[DeitySlot],
        current_tick: int,
    ) -> tuple[bool, str, DivineCodexEntry | None]:
        """World Goddess + >= 3/5 Daughters may commit non-mechanical text decrees directly."""
        valid_daughters: set[DeitySlot] = {
            "gm_human",
            "gm_elf",
            "gm_dragon",
            "gm_beasthuman",
            "gm_demon",
        }
        unique_approvals: list[DeitySlot] = [d for d in daughter_approvals if d in valid_daughters]

        if len(unique_approvals) < 3:
            return (
                False,
                (
                    f"REJECTED: Non-mechanical decrees require World Goddess + >= 3/5 Daughters, "
                    f"got {len(unique_approvals)}"
                ),
                None,
            )

        entry_id = f"codex_{uuid.uuid4().hex[:8]}"
        entry = DivineCodexEntry(
            entry_id=entry_id,
            title=title,
            text=text,
            category="DECREE",
            parameter_key=None,
            parameter_value_json=None,
            author_slot="world_goddess",
            supporting_daughter_slots=unique_approvals,
            approved_by_god=False,
            created_tick=current_tick,
        )
        self.codex_entries[entry_id] = entry
        return True, "GODDESS_COUNCIL_TEXT_DECREE_COMMITTED", entry

    def submit_parameter_override_proposal(
        self,
        title: str,
        text: str,
        parameter_key: str,
        parameter_value: Any,
        proposer_slot: DeitySlot,
        co_sponsors: list[DeitySlot],
        current_tick: int,
    ) -> tuple[bool, str, DivineCodexProposalRecord | None]:
        """
        Submits an engine parameter override proposal to God (Admin).
        Proposer must be World Goddess (alone) OR all 4 Daughters unanimously (4/4).
        """
        valid_daughters = {"gm_human", "gm_elf", "gm_dragon", "gm_beasthuman", "gm_demon"}

        if proposer_slot == "world_goddess":
            # World Goddess alone can submit proposal to God
            pass
        elif proposer_slot in valid_daughters:
            # Daughters must be 5/5 unanimous
            all_sponsors = set(co_sponsors) | {proposer_slot}
            if not valid_daughters.issubset(all_sponsors):
                return (
                    False,
                    (
                        "REJECTED: Parameter override proposals from Daughters require "
                        f"all 5 Daughters unanimously, got {len(all_sponsors)}/5"
                    ),
                    None,
                )
        else:
            return False, "REJECTED: only World Goddess or 5/5 Daughters may submit proposals", None

        proposal_id = f"codex_prop_{uuid.uuid4().hex[:8]}"
        proposal = DivineCodexProposalRecord(
            proposal_id=proposal_id,
            title=title,
            text=text,
            parameter_key=parameter_key,
            parameter_value_json=json.dumps(parameter_value),
            proposer_slot=proposer_slot,
            co_sponsors=co_sponsors,
            status="PENDING_GOD",
            submitted_tick=current_tick,
            resolved_tick=None,
        )
        self.codex_proposals[proposal_id] = proposal
        return True, "PROPOSAL_SUBMITTED_TO_GOD", proposal

    def approve_codex_proposal_by_god(
        self,
        proposal_id: str,
        current_tick: int,
    ) -> tuple[bool, str, DivineCodexEntry | None]:
        """God (Admin) approves and applies parameter override proposal."""
        if proposal_id not in self.codex_proposals:
            return False, "PROPOSAL_NOT_FOUND", None

        prop = self.codex_proposals[proposal_id]
        if prop.status != "PENDING_GOD":
            return False, f"PROPOSAL_NOT_PENDING: status is {prop.status}", None

        prop.status = "APPROVED"
        prop.resolved_tick = current_tick

        param_val = json.loads(prop.parameter_value_json)
        self.live_engine_overrides[prop.parameter_key] = param_val

        entry_id = f"codex_{uuid.uuid4().hex[:8]}"
        entry = DivineCodexEntry(
            entry_id=entry_id,
            title=prop.title,
            text=prop.text,
            category="PARAMETER_OVERRIDE",
            parameter_key=prop.parameter_key,
            parameter_value_json=prop.parameter_value_json,
            author_slot=prop.proposer_slot,
            supporting_daughter_slots=prop.co_sponsors,
            approved_by_god=True,
            created_tick=current_tick,
        )
        self.codex_entries[entry_id] = entry
        return True, "PROPOSAL_APPROVED_AND_APPLIED_BY_GOD", entry

    def reject_codex_proposal_by_god(
        self,
        proposal_id: str,
        current_tick: int,
    ) -> tuple[bool, str, DivineCodexProposalRecord | None]:
        """God (Admin) rejects a pending parameter override proposal."""
        if proposal_id not in self.codex_proposals:
            return False, "PROPOSAL_NOT_FOUND", None

        prop = self.codex_proposals[proposal_id]
        if prop.status != "PENDING_GOD":
            return False, f"PROPOSAL_NOT_PENDING: status is {prop.status}", None

        prop.status = "REJECTED"
        prop.resolved_tick = current_tick
        return True, "PROPOSAL_REJECTED_BY_GOD", prop
