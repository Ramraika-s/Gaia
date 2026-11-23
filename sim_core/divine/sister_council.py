"""
sim_core/divine/sister_council.py
1-on-1 sister dialogues, 5-Sister Council resolutions, Divine Truces,
and World Goddess mediation.
Follows DIVINE_HIERARCHY_SPEC.md Section 5.
"""

from __future__ import annotations

import uuid

from sim_core.divine.hierarchy import DivineHierarchyManager
from sim_core.schemas import DeitySlot, SisterCouncilMessage


class SisterCouncilEngine:
    """Orchestrates structured diplomatic dialogue between the 5 God-Mothers and World Goddess."""

    def __init__(self, hierarchy: DivineHierarchyManager) -> None:
        self.hierarchy = hierarchy
        self.messages: list[SisterCouncilMessage] = []

    def propose_truce(
        self,
        sender_slot: DeitySlot,
        target_slot: DeitySlot,
        day: int,
        tick: int,
    ) -> tuple[bool, SisterCouncilMessage]:
        """
        Two sisters negotiate a 7-game-day Divine Truce blocking wartime WARD_DEFENDERS.
        Succeeds if both sisters possess diplomacy >= 0.50.
        """
        sender = self.hierarchy.get_deity(sender_slot)
        target = self.hierarchy.get_deity(target_slot)

        msg_id = f"truce_{day}_{tick}_{uuid.uuid4().hex[:6]}"
        accepted = sender.personality.diplomacy >= 0.50 and target.personality.diplomacy >= 0.50

        if accepted:
            if target_slot not in sender.active_truce_with:
                sender.active_truce_with.append(target_slot)
            if sender_slot not in target.active_truce_with:
                target.active_truce_with.append(sender_slot)
            resolution = (
                f"DIVINE_TRUCE_ESTABLISHED: 7-day non-intervention pact between "
                f"{sender.bestowed_name} and {target.bestowed_name}."
            )
        else:
            resolution = (
                f"DIVINE_TRUCE_REJECTED: Diplomatic terms declined between "
                f"{sender.bestowed_name} and {target.bestowed_name}."
            )

        msg = SisterCouncilMessage(
            message_id=msg_id,
            day=day,
            tick=tick,
            sender_slot=sender_slot,
            recipient_slots=[target_slot],
            topic="DIVINE_TRUCE",
            summary=f"{sender.bestowed_name} proposed a Divine Truce to {target.bestowed_name}.",
            resolution=resolution,
        )
        self.messages.append(msg)
        return accepted, msg

    def handle_covenant_breach(
        self,
        aggressor_slot: DeitySlot,
        victim_slot: DeitySlot,
        day: int,
        tick: int,
    ) -> SisterCouncilMessage:
        """
        World Goddess mediation on Non-Aggression Covenant breach:
        Rebukes aggressor, applies a 1-game-day intervention freeze, and logs incident.
        """
        aggressor = self.hierarchy.get_deity(aggressor_slot)
        victim = self.hierarchy.get_deity(victim_slot)
        goddess = self.hierarchy.get_deity("world_goddess")

        # 1-day penalty freeze
        aggressor.intervention_cooldown_until_tick = tick + 10800

        msg_id = f"breach_{day}_{tick}_{uuid.uuid4().hex[:6]}"
        summary = (
            f"World Goddess {goddess.bestowed_name} convened emergency council: "
            f"{aggressor.bestowed_name} attempted forbidden offensive miracle "
            f"against mortals of {victim.bestowed_name}."
        )
        resolution = (
            f"COVENANT_REBUKE_ISSUED: {aggressor.bestowed_name} intervention rights frozen "
            f"for 1 Game Day. Total rebukes: {aggressor.covenant_rebukes}."
        )

        msg = SisterCouncilMessage(
            message_id=msg_id,
            day=day,
            tick=tick,
            sender_slot="world_goddess",
            recipient_slots=[aggressor_slot, victim_slot],
            topic="COVENANT_BREACH",
            summary=summary,
            resolution=resolution,
        )
        self.messages.append(msg)
        return msg

    def record_dragon_provocation(
        self,
        provoker_slot: DeitySlot,
        dragon_slot: DeitySlot,
        day: int,
        tick: int,
        settlement_name: str,
    ) -> SisterCouncilMessage:
        """Logs Dragon Mother warning to mortal patron deity after sanctuary provocation."""
        provoker = self.hierarchy.get_deity(provoker_slot)
        dragon = self.hierarchy.get_deity(dragon_slot)

        msg_id = f"prov_{day}_{tick}_{uuid.uuid4().hex[:6]}"
        msg = SisterCouncilMessage(
            message_id=msg_id,
            day=day,
            tick=tick,
            sender_slot=dragon_slot,
            recipient_slots=[provoker_slot],
            topic="DRAGON_PROVOCATION",
            summary=(
                f"{dragon.bestowed_name} issued stern warning to {provoker.bestowed_name}: "
                f"Mortals from {settlement_name} trespassed into mountain sanctuary "
                "and provoked True Dragon defense."
            ),
            resolution="SISTERLY_WARNING: Advise mortals to respect mountain borders.",
        )
        self.messages.append(msg)
        return msg
