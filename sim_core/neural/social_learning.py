"""
sim_core/neural/social_learning.py
Four-channel social learning system:
1. Parental Care & Teaching (+0.04 * (1 + teach_skill))
2. Peer Observation (+0.015 * trust * stage_plasticity)
3. World Library Consultation (+0.08 up to 0.60)
4. Cultural Tradition Transmission
Follows NEURAL_AND_LIFECYCLE_SPEC.md Section 5.2.
"""

from __future__ import annotations

from sim_core.schemas import Stage

STAGE_PLASTICITY: dict[Stage | str, float] = {
    "INFANT": 1.5,
    "CHILD": 1.0,
    "ADULT": 0.5,
    "ELDER": 0.2,
}


class SocialLearningSystem:
    """Handles skill advancement and cultural transmission across four social channels."""

    @staticmethod
    def apply_parental_teaching(
        child_skills: dict[str, float],
        skill_name: str,
        parent_teach_skill: float,
        dist_meters: float,
        max_dist: float = 6.0,
    ) -> float:
        """
        Channel 1: Parental Care & Teaching.
        Nearby parent (dist <= 6m) boosts child skill by +0.04 * (1 + parent_teach_skill).
        Clamped to [0.0, 1.0].
        Returns the delta applied.
        """
        if dist_meters > max_dist:
            return 0.0

        current = child_skills.get(skill_name, 0.0)
        delta = 0.04 * (1.0 + max(0.0, parent_teach_skill))
        new_val = min(1.0, current + delta)
        child_skills[skill_name] = new_val
        return new_val - current

    @staticmethod
    def apply_peer_observation(
        observer_skills: dict[str, float],
        peer_skills: dict[str, float],
        skill_name: str,
        trust: float,
        observer_stage: Stage | str,
        peer_success: bool = True,
    ) -> float:
        """
        Channel 2: Peer Observation.
        Observing a trusted neighbor (trust > 0.2) succeed grants:
        +0.015 * trust * plasticity(stage), capped at peer's mastery.
        Returns the delta applied.
        """
        if not peer_success or trust <= 0.2:
            return 0.0

        current = observer_skills.get(skill_name, 0.0)
        peer_mastery = peer_skills.get(skill_name, 0.0)
        if current >= peer_mastery:
            return 0.0

        plasticity = STAGE_PLASTICITY.get(observer_stage, 1.0)
        delta = 0.015 * trust * plasticity
        new_val = min(peer_mastery, current + delta)
        observer_skills[skill_name] = new_val
        return new_val - current

    @staticmethod
    def apply_library_reading(
        agent_skills: dict[str, float],
        skill_name: str,
        is_elder_approved: bool,
        already_read_book_ids: set[str],
        book_id: str,
        boost_amount: float = 0.08,
        mastery_ceiling: float = 0.60,
    ) -> float:
        """
        Channel 3: World Library Consultation.
        Reading an Elder-approved entry grants a one-time +0.08 boost up to 0.60 mastery.
        Returns the delta applied.
        """
        if not is_elder_approved or book_id in already_read_book_ids:
            return 0.0

        current = agent_skills.get(skill_name, 0.0)
        if current >= mastery_ceiling:
            already_read_book_ids.add(book_id)
            return 0.0

        delta = min(boost_amount, mastery_ceiling - current)
        agent_skills[skill_name] = current + delta
        already_read_book_ids.add(book_id)
        return delta

    @staticmethod
    def transmit_cultural_tradition(
        agent_stage: Stage | str,
        personal_traditions: set[str],
        observed_tradition_id: str,
        event_active: bool,
    ) -> bool:
        """
        Channel 4: Cultural Tradition Transmission.
        Infants and children adopt local traditions observed during trigger events.
        Returns True if newly adopted.
        """
        if agent_stage not in ("INFANT", "CHILD") or not event_active:
            return False

        if observed_tradition_id not in personal_traditions:
            personal_traditions.add(observed_tradition_id)
            return True
        return False
