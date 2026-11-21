"""
sim_core/persistence/world_goddess.py
WorldGoddessCritic: Global critic, RBAC matrix validator, and verdict feedback emitter.
Enforces non-negotiable architectural invariants and biological/institutional rules.
"""

from __future__ import annotations

from sim_core.schemas import CommitProposal, CriticVerdict


class WorldGoddessCritic:
    """
    World Goddess Critic enforcing the complete v3.0 validation and RBAC matrix.
    Evaluates proposals in RAM immediately and emits a CriticVerdict.
    """

    def __init__(self) -> None:
        self.audit_log: list[CriticVerdict] = []

    def evaluate(self, proposal: CommitProposal) -> CriticVerdict:
        """
        Evaluates a CommitProposal against all domain invariants.
        Returns CriticVerdict(status="SUCCESS"|"FAILURE", reason=...).
        """
        # Divine bypass granted strictly for direct God actions
        if proposal.bypass_god_check:
            verdict = CriticVerdict(
                proposal_id=proposal.proposal_id,
                kind=proposal.kind,
                actor_id=proposal.actor_id,
                status="SUCCESS",
                reason="Approved: divine bypass granted (God origin)",
                committed_tick=proposal.tick,
            )
            self.audit_log.append(verdict)
            return verdict

        kind = proposal.kind
        payload = proposal.payload

        # ---------------------------------------------------------------------
        # 1. CONCEPTION
        # ---------------------------------------------------------------------
        if kind == "CONCEPTION":
            p1_gender = payload.get("parent1_gender")
            p2_gender = payload.get("parent2_gender")
            if not p1_gender or not p2_gender or p1_gender == p2_gender:
                return self._reject(proposal, "Rejected: mating requires one BOY and one GIRL")

            # Check Dragon form constraint
            p1_race = payload.get("parent1_race")
            p2_race = payload.get("parent2_race")
            if p1_race == "DRAGON" and payload.get("parent1_dragon_form") == "TRUE_DRAGON":
                return self._reject(proposal, "Rejected: Dragon must be in HUMANOID_DRAGON form")
            if p2_race == "DRAGON" and payload.get("parent2_dragon_form") == "TRUE_DRAGON":
                return self._reject(proposal, "Rejected: Dragon must be in HUMANOID_DRAGON form")

            # Mother pregnancy check
            if payload.get("mother_pregnant_ticks_remaining", 0) > 0:
                return self._reject(proposal, "Rejected: mother already pregnant")

            # Cross-species conception roll (50% chance)
            is_cross_species = (p1_race != p2_race)
            if is_cross_species:
                roll = payload.get("conception_roll")
                if roll is not None and roll > 0.50:
                    return self._reject(
                        proposal,
                        "Conception did not occur (cross-species 50% roll)",
                    )

            return self._approve(proposal, "Conception approved")

        # ---------------------------------------------------------------------
        # 2. BIRTH
        # ---------------------------------------------------------------------
        if kind == "BIRTH":
            if payload.get("pregnant_ticks_remaining", 0) > 0:
                return self._reject(proposal, "Rejected: gestation incomplete")

            if payload.get("is_cross_species_pregnancy", False):
                survival_roll = payload.get("birth_survival_roll")
                if survival_roll is not None and survival_roll > 0.60:
                    return self._reject(
                        proposal,
                        "Birth complication: cross-species infant did not survive",
                    )

            return self._approve(proposal, "Birth approved and infant slot allocated")

        # ---------------------------------------------------------------------
        # 3. PATRON_CHOICE (Mixed-race age-10 milestone)
        # ---------------------------------------------------------------------
        if kind == "PATRON_CHOICE":
            if not payload.get("secondary_heritage_race"):
                return self._reject(
                    proposal,
                    "Rejected: agent is not an uncommitted mixed-race child",
                )

            target = payload.get("target_godmother_slot")
            p1_gm = payload.get("parent1_godmother_slot")
            p2_gm = payload.get("parent2_godmother_slot")

            if target not in (p1_gm, p2_gm):
                return self._reject(
                    proposal,
                    "Rejected: target God-Mother is not a parental patron",
                )

            bio_age = payload.get("biological_age_years", 0.0)
            if bio_age < 10.0:
                return self._reject(
                    proposal,
                    f"Rejected: biological age {bio_age:.1f} is below age 10 milestone",
                )

            return self._approve(proposal, "Patron God-Mother locked permanently")

        # ---------------------------------------------------------------------
        # 4. CREDIT_TRANSFER (Strict Closed-Loop Double-Entry)
        # ---------------------------------------------------------------------
        if kind == "CREDIT_TRANSFER":
            amount = payload.get("amount", 0.0)
            if amount <= 0.0:
                return self._reject(proposal, "Rejected: non-positive transfer amount")

            sender_credits = payload.get("sender_credits", 0.0)
            if sender_credits < amount:
                return self._reject(proposal, "Rejected: insufficient funds")

            return self._approve(proposal, "Double-entry transfer approved")

        # ---------------------------------------------------------------------
        # 5. TWO-BOOK GOVERNANCE: LIBRARY_ENTRY, LIBRARY_VOTE, DIVINE_CODEX
        # ---------------------------------------------------------------------
        if kind == "LIBRARY_ENTRY":
            author_type = payload.get("author_type")
            actor = proposal.actor_id or ""

            # Case A: World Goddess edit (requires >= 1 Daughter approval)
            if author_type == "WORLD_GODDESS" or actor == "world_goddess":
                daughter_approvals = payload.get("daughter_approvals_count", 0)
                if daughter_approvals < 1:
                    return self._reject(
                        proposal,
                        "Unauthorized: World Goddess requires >= 1 Daughter approval",
                    )
                return self._approve(
                    proposal, "World Library entry approved by World Goddess and Daughter(s)"
                )

            # Case B: Daughters alone (requires >50%, i.e. >= 3/5 Daughters voting approve)
            if author_type == "DAUGHTERS" or (
                actor in ("gm_human", "gm_elf", "gm_dragon", "gm_beasthuman", "gm_demon")
                and not payload.get("with_world_goddess", False)
            ):
                daughter_approvals = payload.get("daughter_approvals_count", 0)
                if daughter_approvals < 3:
                    return self._reject(
                        proposal,
                        "Unauthorized: Daughters alone require >50% (at least 3 of 5) approvals",
                    )
                return self._approve(
                    proposal, "World Library entry approved by Daughters Council (>50%)"
                )

            # Case C: Mortal Proposal
            status = payload.get("proposal_status")
            if status == "EXPIRED":
                return self._reject(
                    proposal,
                    "Rejected: proposal expired after 30 days without God-Mother approval",
                )
            if status == "BLOCKED_BY_DAUGHTERS":
                return self._reject(proposal, "Rejected: blocked by Daughters (>= 3/5 objections)")

            # Check Mortal Elders consensus (> 50%)
            approvals = payload.get("elder_approvals_count", 0)
            total_elders = payload.get("total_appointed_elders", 0)
            if total_elders == 0 or approvals * 2 <= total_elders:
                return self._reject(
                    proposal,
                    "Unauthorized: requires >50% Council of Elders consensus",
                )

            # Check God-Mother review
            gm_approvals = payload.get("godmother_approvals_count")
            gm_objections = payload.get("godmother_objections_count", 0)

            if gm_approvals is not None:
                if gm_approvals < 1 and status != "APPROVED":
                    return self._reject(proposal, "Rejected: requires >= 1 God-Mother approval")
            elif status == "PENDING_GODMOTHERS":
                return self._reject(proposal, "Rejected: requires >= 1 God-Mother approval")

            if gm_objections >= 3:
                return self._reject(proposal, "Rejected: blocked by Daughters (>= 3/5 objections)")

            proficiency = payload.get("author_proficiency", 0.0)
            is_scripture = payload.get("is_scripture", False)
            if not is_scripture and proficiency < 0.70:
                return self._reject(proposal, "Rejected: insufficient mastery (<0.70)")

            return self._approve(
                proposal, "World Library entry approved by Elders and God-Mothers"
            )

        if kind == "LIBRARY_VOTE":
            voter_type = payload.get("voter_type", "ELDER")
            if voter_type == "ELDER":
                if not payload.get("is_appointed_elder", False):
                    return self._reject(
                        proposal,
                        "Unauthorized: voter is not an Appointed Library Elder",
                    )
            elif voter_type == "GOD_MOTHER":
                if not payload.get("is_god_mother", False):
                    return self._reject(
                        proposal,
                        "Unauthorized: voter is not a Racial God-Mother",
                    )

            if payload.get("has_already_voted", False):
                return self._reject(proposal, "Rejected: duplicate vote")

            return self._approve(proposal, f"{voter_type.title()} vote recorded")

        if kind == "DIVINE_CODEX_DECREE":
            # Check parameter override attempt
            has_param = (
                payload.get("is_parameter_override", False)
                or payload.get("parameter_key") is not None
                or payload.get("category") == "PARAMETER_OVERRIDE"
            )
            if has_param:
                return self._reject(
                    proposal,
                    "Unauthorized: parameter overrides require direct God execution (Option B)",
                )

            # Non-mechanical text decree requires World Goddess + >= 3/4 Daughters
            actor = proposal.actor_id or ""
            approvals_list = payload.get("supporting_daughter_slots", [])
            daughter_approvals = payload.get(
                "daughter_approvals_count",
                len(approvals_list) if isinstance(approvals_list, list) else 0,
            )
            if actor == "world_goddess" and daughter_approvals >= 3:
                return self._approve(
                    proposal, "Divine Codex decree approved by World Goddess and Daughters Council"
                )

            return self._reject(
                proposal,
                "Unauthorized: non-mechanical decrees require World Goddess + >=3/5 Daughters",
            )

        if kind == "DIVINE_CODEX_PROPOSAL":
            proposer = proposal.actor_id or payload.get("proposer_slot", "")
            if proposer == "world_goddess":
                return self._approve(
                    proposal, "Divine Codex proposal submitted to God by World Goddess"
                )
            if proposer in ("gm_human", "gm_elf", "gm_dragon", "gm_beasthuman", "gm_demon"):
                co_sponsors = payload.get("co_sponsors", [])
                total_daughters = (
                    len(set(co_sponsors) | {proposer}) if isinstance(co_sponsors, list) else 0
                )
                co_sponsors_count = payload.get("co_sponsors_count", total_daughters)
                if co_sponsors_count >= 5 or payload.get("is_unanimous_daughters", False):
                    return self._approve(
                        proposal,
                        "Divine Codex proposal submitted to God by unanimous Daughters Council",
                    )
                return self._reject(
                    proposal,
                    "Unauthorized: proposals require World Goddess alone or unanimous 5/5 "
                    "Daughters",
                )
            return self._reject(
                proposal, "Unauthorized: mortals cannot submit Divine Codex proposals"
            )

        # ---------------------------------------------------------------------
        # 6. SETTLEMENT_UPDATE & APPEALS
        # ---------------------------------------------------------------------
        if kind == "SETTLEMENT_UPDATE":
            action = payload.get("sub_action")
            if action == "APPOINT_LIBRARY_ELDER":
                current_elders = payload.get("current_nation_elders_count", 0)
                if current_elders >= 2:
                    return self._reject(
                        proposal,
                        "Rejected: nation already has maximum 2 Library Elders",
                    )
            return self._approve(proposal, "Settlement update approved")

        if kind == "SETTLEMENT_APPEAL":
            appeal_kind = payload.get("appeal_kind")
            if appeal_kind == "NEUTRAL_FREE_CITY":
                races_over_15 = payload.get("qualifying_races_count", 0)
                if races_over_15 < 2:
                    return self._reject(
                        proposal,
                        "Rejected: Neutral Free City requires >=2 races at >=15% share",
                    )
            return self._approve(proposal, "Settlement appeal approved")

        # ---------------------------------------------------------------------
        # 7. JUDICIARY_RULING
        # ---------------------------------------------------------------------
        if kind == "JUDICIARY_RULING":
            combat_context = payload.get("combat_context")
            ruling = payload.get("ruling")

            # Verified defense or war context MUST be acquitted
            if combat_context in ("SELF_DEFENSE", "DEFENDING_KIN_OR_TOWN", "ACTIVE_WAR"):
                if ruling != "ACQUITTED":
                    return self._reject(
                        proposal,
                        "Rejected: unlawful conviction on verified self-defense/war context",
                    )

            return self._approve(proposal, "Judiciary ruling validated")

        # ---------------------------------------------------------------------
        # 8. NAME_DEITY
        # ---------------------------------------------------------------------
        if kind == "NAME_DEITY":
            return self._reject(proposal, "Unauthorized: only God may bestow deity names")

        # ---------------------------------------------------------------------
        # 9. WAR_DECLARATION
        # ---------------------------------------------------------------------
        if kind == "WAR_DECLARATION":
            if payload.get("is_neutral_free_city", False):
                return self._reject(
                    proposal,
                    "Rejected: Neutral Free Cities cannot declare offensive war",
                )
            return self._approve(proposal, "War declaration approved")

        # Default fallback approval for other registered kinds
        return self._approve(proposal, f"Approved {kind}")

    def _approve(self, proposal: CommitProposal, reason: str) -> CriticVerdict:
        verdict = CriticVerdict(
            proposal_id=proposal.proposal_id,
            kind=proposal.kind,
            actor_id=proposal.actor_id,
            status="SUCCESS",
            reason=reason,
            committed_tick=proposal.tick,
        )
        self.audit_log.append(verdict)
        return verdict

    def _reject(self, proposal: CommitProposal, reason: str) -> CriticVerdict:
        verdict = CriticVerdict(
            proposal_id=proposal.proposal_id,
            kind=proposal.kind,
            actor_id=proposal.actor_id,
            status="FAILURE",
            reason=reason,
            committed_tick=None,
        )
        self.audit_log.append(verdict)
        return verdict
