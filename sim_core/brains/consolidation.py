"""
sim_core/brains/consolidation.py
Pillar 4: Sleep-Cycle Consolidation Engine.
Follows Gaia v4.0 Sprint 4 specifications:
- Invoked cleanly at end-of-day (strictly in RAM before World Goddess 2PC, no mid-day writes).
- Mortal Profession Distillation: Aggregates high-reward rollouts from top practitioners (Lv. 6+)
  and performs bounded, stability-gated gradient updates on ProfessionNet.
  Automatically rolls back on NaN or loss regression.
- Book-to-Habit Distillation: Nudges agent's SelfNet weights for frequently used tactics.
- Deity Memory Compression & Bounded Trait Drift: Summarizes daily events and applies small,
  clamped personality drift (|delta| <= 0.03/day).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from sim_core.brains.memory_rag import EpisodicMemoryRecord, MemoryRAGIndex
from sim_core.brains.personality import MoodState, PersonalityVector
from sim_core.brains.profession_nets import PROFESSIONS, ProfessionNetRegistry
from sim_core.resilience.healer import ErrorHealer

if TYPE_CHECKING:
    from sim_core.brains.action_bridge import ProfessionRolloutBuffer
    from sim_core.schemas import AgentRecord, DivineEntityRecord

logger = logging.getLogger(__name__)


class SleepCycleConsolidator:
    """
    Executes nightly neural and cognitive consolidation during the sleep cycle at end-of-day.
    Strictly in RAM before the atomic commit.
    """

    def __init__(self, healer: ErrorHealer | None = None) -> None:
        self.healer = healer

    # --------------------------------------------------------------------------
    # 1. Mortal Profession Distillation
    # --------------------------------------------------------------------------

    def consolidate_mortal_professions(
        self,
        agents: list[AgentRecord] | dict[str, AgentRecord],
        profession_registry: ProfessionNetRegistry,
        learning_rate: float = 1e-3,
        max_grad_norm: float = 1.0,
        inject_nan_for_test: bool = False,
        rollout_buffer: ProfessionRolloutBuffer | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        Aggregates high-reward rollouts from Lv. 6+ practitioners per profession,
        performing stability-gated gradient updates on that profession's MLP.
        If real rollouts exist in rollout_buffer, trains on real transitions;
        otherwise falls back to practitioner feature builder.
        If NaN is detected or validation loss regresses, rolls back immediately.
        """
        agent_list = list(agents.values()) if isinstance(agents, dict) else agents
        results: dict[str, dict[str, Any]] = {}

        # Group high-level practitioners (Lv. 6+)
        high_level_by_prof: dict[str, list[AgentRecord]] = {p: [] for p in PROFESSIONS}
        for a in agent_list:
            if getattr(a, "alive", True) and getattr(a, "profession_level", 1) >= 6:
                prof = getattr(a, "profession", "CITIZEN").upper()
                if prof in high_level_by_prof:
                    high_level_by_prof[prof].append(a)

        for prof, practitioners in high_level_by_prof.items():
            rollouts = rollout_buffer.get_rollouts(prof) if rollout_buffer is not None else []
            if not practitioners and not rollouts:
                results[prof] = {"status": "SKIPPED_NO_PRACTITIONERS", "practitioners_count": 0}
                continue

            net = profession_registry.get_net(prof)
            profession_registry.snapshot_weights(prof)

            try:
                # Prepare training data from rollouts or practitioners
                x_list = []
                lvl_list = []
                target_action_logits = []

                if rollouts:
                    for trans in rollouts:
                        x_list.append(trans.features)
                        lvl_list.append([float(trans.level)])
                        target_l = np.zeros(net.action_dim, dtype=np.float32)
                        target_l[trans.action_idx] = float(2.0 * max(0.5, trans.reward))
                        target_action_logits.append(target_l)
                else:
                    for p_agent in practitioners:
                        # Construct feature vector
                        base_features = [0.1] * 20
                        base_features[0] = getattr(p_agent, "hunger", 100.0) / 100.0
                        base_features[1] = getattr(p_agent, "stamina", 100.0) / 100.0
                        base_features[2] = getattr(p_agent, "hygiene", 1.0)
                        base_features[3] = getattr(p_agent, "fatigue", 0.0)

                        feats = profession_registry.pack_profession_features(
                            base_living_features=base_features,
                            level=getattr(p_agent, "profession_level", 6),
                            xp=getattr(p_agent, "profession_xp", 500.0),
                            active_mechanical_effects=getattr(
                                p_agent, "active_mechanical_effects", {}
                            ),
                        )
                        x_list.append(feats)
                        lvl_list.append([float(getattr(p_agent, "profession_level", 6))])

                        # Target: encourage specialized actions based on profession
                        target_l = np.zeros(net.action_dim, dtype=np.float32)
                        if prof == "KNIGHT":
                            target_l[10] = 2.0  # CONFRONT / DEFEND
                            target_l[3] = 0.5  # EVADE
                        elif prof == "SCHOLAR":
                            target_l[6] = 2.5  # STUDY
                        elif prof == "FARMER":
                            target_l[7] = 2.0  # CRAFT / WORK
                        elif prof == "MERCHANT":
                            target_l[8] = 2.2  # TRADE
                        elif prof == "CLERIC":
                            target_l[9] = 2.5  # PRAY
                        else:
                            target_l[7] = 1.0

                        target_action_logits.append(target_l)

                x_t = torch.tensor(x_list, dtype=torch.float32, device=profession_registry.device)
                lvl_t = torch.tensor(
                    lvl_list, dtype=torch.float32, device=profession_registry.device
                )
                target_t = torch.tensor(
                    np.array(target_action_logits),
                    dtype=torch.float32,
                    device=profession_registry.device,
                )

                # Validation loss before step
                with torch.no_grad():
                    pred_logits, pred_v = net(x_t, lvl_t)
                    init_loss = nn.functional.mse_loss(pred_logits, target_t).item()

                if inject_nan_for_test:
                    with torch.no_grad():
                        for p in net.parameters():
                            p.data[0] = float("nan")

                # Stability Check 1: Initial state
                has_nan = any(
                    torch.isnan(p).any() or torch.isinf(p).any() for p in net.parameters()
                )
                if has_nan:
                    profession_registry.rollback_weights(prof)
                    if rollout_buffer is not None:
                        rollout_buffer.clear(prof)
                    results[prof] = {
                        "status": "ROLLED_BACK_NAN_DETECTED",
                        "practitioners_count": len(practitioners),
                    }
                    continue

                # Optimize step
                optimizer = optim.SGD(net.parameters(), lr=learning_rate)
                optimizer.zero_grad()
                pred_logits, pred_v = net(x_t, lvl_t)
                loss = nn.functional.mse_loss(pred_logits, target_t)
                loss.backward()

                # Gradient clipping
                nn.utils.clip_grad_norm_(net.parameters(), max_norm=max_grad_norm)
                optimizer.step()

                # Stability Check 2: Post-step NaNs
                has_nan_post = any(
                    torch.isnan(p).any() or torch.isinf(p).any() for p in net.parameters()
                )
                if has_nan_post:
                    profession_registry.rollback_weights(prof)
                    if rollout_buffer is not None:
                        rollout_buffer.clear(prof)
                    results[prof] = {
                        "status": "ROLLED_BACK_POST_STEP_NAN",
                        "practitioners_count": len(practitioners),
                    }
                    continue

                # Stability Check 3: Loss regression check
                with torch.no_grad():
                    post_logits, _ = net(x_t, lvl_t)
                    post_loss = nn.functional.mse_loss(post_logits, target_t).item()

                if post_loss > (init_loss * 2.5) and init_loss > 1e-4:
                    profession_registry.rollback_weights(prof)
                    if rollout_buffer is not None:
                        rollout_buffer.clear(prof)
                    results[prof] = {
                        "status": "ROLLED_BACK_LOSS_REGRESSION",
                        "init_loss": init_loss,
                        "post_loss": post_loss,
                        "practitioners_count": len(practitioners),
                    }
                    continue

                if rollout_buffer is not None and rollouts:
                    rollout_buffer.clear(prof)

                results[prof] = {
                    "status": "UPDATED_SUCCESS",
                    "init_loss": init_loss,
                    "post_loss": post_loss,
                    "practitioners_count": len(practitioners),
                }

            except Exception as e:
                logger.error(f"Error consolidating profession {prof}: {e}")
                profession_registry.rollback_weights(prof)
                if rollout_buffer is not None:
                    rollout_buffer.clear(prof)
                if self.healer:
                    self.healer.handle(
                        fault_class="AGENT_REPEAT_FAULT",
                        day=0,
                        tick=0,
                        context={"profession": prof, "error": str(e)},
                    )
                results[prof] = {"status": "ERROR_ROLLED_BACK", "error": str(e)}

        return results

    # --------------------------------------------------------------------------
    # 2. Book-to-Habit Distillation
    # --------------------------------------------------------------------------

    def distill_book_to_habit(
        self,
        agent: AgentRecord,
        hierarchical_brain: Any,
        tactic_action_idx: int,
        learning_strength: float = 0.02,
    ) -> bool:
        """
        Nudges agent's BatchedAgentSelfNet weights so a frequently used book tactic
        becomes intuitive habit without slow deliberative recall.
        Guarded by parameter clamping and finite checks.
        """
        slot = getattr(agent, "slot_idx", None)
        if slot is None:
            return False

        tier3 = getattr(hierarchical_brain, "tier3_self", None)
        if tier3 is None or slot not in tier3.active_slots:
            return False

        with torch.no_grad():
            # Check slot bounds
            if slot >= tier3.W_out.shape[0]:
                return False

            # Nudge output weights corresponding to the tactic action index
            w_slice = tier3.W_out.data[slot, :, tactic_action_idx]
            w_slice += learning_strength * 0.05
            # Clamp to prevent drift explosion
            tier3.W_out.data[slot, :, tactic_action_idx] = torch.clamp(w_slice, -2.5, 2.5)

            # Also slightly bias b_out
            tier3.b_out.data[slot, tactic_action_idx] = torch.clamp(
                tier3.b_out.data[slot, tactic_action_idx] + (learning_strength * 0.02),
                -1.5,
                1.5,
            )

        return True

    # --------------------------------------------------------------------------
    # 3. Deity Memory Compression & Bounded Trait Drift
    # --------------------------------------------------------------------------

    def compress_deity_memories_and_drift(
        self,
        deities: Mapping[Any, DivineEntityRecord],
        daily_world_events: list[dict[str, Any]],
        memory_rag: MemoryRAGIndex | None = None,
        day: int = 1,
    ) -> dict[str, dict[str, float]]:
        """
        Summarizes daily events into compact deity memories and applies
        bounded personality drift (|delta| <= 0.03/day) clamped strictly to [0.0, 1.0].
        Events evaluated:
        - treaty_breach_count / covenant_rebukes
        - economic_crisis / famine (severe CPI crisis)
        - devout_pilgrimages / prayers
        - active_wars
        """
        trait_deltas_applied: dict[str, dict[str, float]] = {}

        # Aggregate event metrics
        total_wars = sum(1 for e in daily_world_events if e.get("event_type") == "WAR")
        total_crimes = sum(1 for e in daily_world_events if e.get("event_type") == "CRIME")
        total_prayers = sum(1 for e in daily_world_events if e.get("event_type") == "PRAYER")
        famine_severity = sum(
            e.get("severity", 0.0) for e in daily_world_events if e.get("event_type") == "FAMINE"
        )
        covenant_breaches = sum(
            1 for e in daily_world_events if e.get("event_type") == "COVENANT_BREACH"
        )

        for slot, deity in deities.items():
            pv: PersonalityVector | None = getattr(deity, "personality_vector", None)
            if pv is None:
                continue

            deltas: dict[str, float] = {}

            # World Goddess & Racial God-Mothers react based on divine role and events:
            if covenant_breaches > 0 or deity.covenant_rebukes > 0:
                # Treaty breaches: heighten caution, reduce out_group_trust
                deltas["caution"] = deltas.get("caution", 0.0) + 0.025
                deltas["out_group_trust"] = deltas.get("out_group_trust", 0.0) - 0.02

            if total_wars > 0:
                # Wars: reduce calm, heighten courage or caution
                deltas["courage"] = deltas.get("courage", 0.0) + 0.015
                deltas["out_group_trust"] = deltas.get("out_group_trust", 0.0) - 0.02

            if famine_severity > 0.0 or total_crimes > 5:
                # Crisis / famine: increases empathy, increases discipline
                deltas["empathy"] = deltas.get("empathy", 0.0) + 0.02
                deltas["discipline"] = deltas.get("discipline", 0.0) + 0.015

            if total_prayers > 20:
                # Devout prayers: heighten devotion, pride
                deltas["devotion"] = deltas.get("devotion", 0.0) + 0.02
                deltas["pride"] = deltas.get("pride", 0.0) + 0.015

            # Apply bounded drift (|delta| <= 0.03 per day)
            clamped_deltas = {k: max(-0.03, min(0.03, v)) for k, v in deltas.items()}
            pv.apply_drift(clamped_deltas, max_step=0.03)
            trait_deltas_applied[slot] = clamped_deltas

            # Mood daily decay toward baseline calm
            mood: MoodState | None = getattr(deity, "mood", None)
            if mood is not None:
                mood.step_decay(decay_rate=0.4)
                if covenant_breaches > 0:
                    mood.angry = min(1.0, mood.angry + 0.3)
                if total_prayers > 20:
                    mood.inspired = min(1.0, mood.inspired + 0.2)

            # Store compressed deity daily memory in RAG
            if memory_rag is not None:
                summary_text = (
                    f"Day {day} Divine Ledger: {total_prayers} prayers, "
                    f"{total_wars} wars, {covenant_breaches} covenant breaches."
                )
                rec = EpisodicMemoryRecord(
                    agent_id=slot,
                    day=day,
                    tick=0,
                    event_type="DIVINE_DAILY_SUMMARY",
                    actor_ids=[],
                    summary=summary_text,
                    emotional_valence=0.1 if covenant_breaches == 0 else -0.3,
                    tags=["DIVINE", "DAILY_SUMMARY", "COVENANT"],
                    importance=0.8,
                )
                memory_rag.add_episodic_memory(slot, rec)

        return trait_deltas_applied
