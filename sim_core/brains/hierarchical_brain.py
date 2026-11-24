"""
sim_core/brains/hierarchical_brain.py
Pillar 1 (Tier 3): Hierarchical Cognitive Composition Engine.
Composes:
- Tier 1: SharedLivingNet (universal baseline survival & reflex)
- Tier 2: ProfessionNetRegistry (profession expertise Lv. 1–10 + book mechanics)
- Tier 3: BatchedAgentSelfNet (individual 2,048-slab GRU working memory)
- Pillar 3: Evolving Personality & Mood action logit bias
- Life-Stage action masking (Infant 0..5, Child 0..9, Adult/Elder 0..19)
- NaN/Inf self-healing via ErrorHealer.
Executes in < 25 ms/step for 10,000 agents.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import torch
import torch.nn as nn

from sim_core.brains.personality import (
    MoodState,
    PersonalityVector,
)
from sim_core.brains.profession_nets import (
    EFFECT_KEY_TO_CHANNEL,
    ProfessionNetRegistry,
)
from sim_core.brains.shared_living_net import SharedLivingNet
from sim_core.config import SLAB_SIZE
from sim_core.neural.batched_self_net import BatchedAgentSelfNet
from sim_core.neural.shared_net import (
    ALPHA_MOD,
    STAGE_MASK_TENSOR,
    STAGE_NAME_TO_IDX,
)
from sim_core.resilience.healer import ErrorHealer

EFFECT_KEY_MAP: dict[str, int] = {
    "defense": 0,
    "yield_mult": 1,
    "trade_margin": 2,
    "research_rate": 3,
    "faith_gain": 4,
    "stamina_efficiency": 5,
}


class HierarchicalBrain(nn.Module):
    """
    3-Tier Hierarchical Neural Brain composing species-wide living competence,
    profession expertise, individual slab-grown memory, and personality logit biases.
    """

    stage_masks: torch.Tensor
    bias_weight_matrix: torch.Tensor

    def __init__(
        self,
        initial_capacity: int = SLAB_SIZE,
        device: str | torch.device = "cpu",
        healer: ErrorHealer | None = None,
    ) -> None:
        super().__init__()
        self.device = torch.device(device)
        self.healer = healer

        # 3 Tiers
        self.tier1_living = SharedLivingNet().to(self.device)
        self.tier2_profession = ProfessionNetRegistry(device=self.device)
        self.tier3_self = BatchedAgentSelfNet(
            initial_capacity=initial_capacity,
            device=self.device,
            healer=healer,
        )

        # Buffer for stage masks
        self.register_buffer("stage_masks", STAGE_MASK_TENSOR.clone().to(self.device))
        self.register_buffer("bias_weight_matrix", self._build_bias_weights())

    def _build_bias_weights(self) -> torch.Tensor:
        """Constructs (15, 20) linear projection matrix matching compute_action_logit_bias."""
        W = torch.zeros((15, 20), dtype=torch.float32, device=self.device)
        W[10, 0] = 0.4
        W[11, 0] = -0.6
        W[13, 0] = -0.3
        W[3, 2] = 0.6
        W[8, 3] = 0.8
        W[13, 3] = 1.2
        W[11, 3] = -0.4
        W[2, 4] = 0.4
        W[0, 4] = 0.3
        W[1, 5] = 0.9
        W[10, 5] = 0.3
        W[4, 6] = 1.0
        W[3, 6] = 0.4
        W[14, 6] = 0.8
        W[3, 7] = 0.7
        W[2, 7] = 0.5
        W[2, 8] = 0.6
        W[7, 8] = 0.4
        W[5, 9] = 1.2
        W[0, 10] = 1.0
        W[9, 10] = 0.5
        W[8, 10] = -0.8
        W[11, 10] = 1.4
        W[13, 10] = -0.8
        return W

    @torch.no_grad()
    def forward_batch(
        self,
        slot_indices: list[int] | torch.Tensor,
        x_living: torch.Tensor,
        professions: list[str],
        levels: list[int] | torch.Tensor,
        active_effects: list[dict[str, float]],
        stages: list[str],
        personalities: list[PersonalityVector | None] | torch.Tensor | None = None,
        moods: list[MoodState | None] | torch.Tensor | None = None,
        health_ratios: torch.Tensor | None = None,
        hungers: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Executes composed 3-tier forward pass across N scheduled agents:
        Returns:
            masked_logits: (N, 20) action logits with stage masking and personality bias
            values: (N, 1) composed state-value estimate
        """
        N = len(slot_indices) if isinstance(slot_indices, list) else slot_indices.shape[0]
        if N == 0:
            return torch.empty((0, 20), device=self.device), torch.empty((0, 1), device=self.device)

        # 1. Tier 1 Universal Living Net
        l_living, v_living, _ = self.tier1_living(x_living)

        # 2. Tier 2 Grouped Profession Nets (Vectorized Feature Packing)
        delta_l_prof = torch.zeros((N, 20), dtype=torch.float32, device=self.device)
        v_prof_total = torch.zeros((N, 1), dtype=torch.float32, device=self.device)

        x_prof = torch.zeros((N, 28), dtype=torch.float32, device=self.device)
        x_prof[:, :20] = x_living[:, :20]
        if isinstance(levels, torch.Tensor):
            t_levels = levels.view(N, 1).to(self.device)
        else:
            t_levels = torch.as_tensor(levels, dtype=torch.float32, device=self.device).view(N, 1)
        x_prof[:, 20:21] = t_levels / 10.0

        eff_mat = np.zeros((N, 6), dtype=np.float32)
        has_effects = False
        for i, eff in enumerate(active_effects):
            if eff:
                has_effects = True
                for k, v in eff.items():
                    ch = EFFECT_KEY_TO_CHANNEL.get(k)
                    if ch is not None:
                        eff_mat[i, ch] += float(v)
        if has_effects:
            np.clip(eff_mat, -1.0, 1.0, out=eff_mat)
            x_prof[:, 22:28] = torch.from_numpy(eff_mat).to(self.device)

        # Group agent indices by profession for efficient sub-batching
        prof_groups: dict[str, list[int]] = {}
        for i, p in enumerate(professions):
            prof_groups.setdefault(p, []).append(i)

        for p_name, idx_list in prof_groups.items():
            idx_tensor = torch.as_tensor(idx_list, dtype=torch.long, device=self.device)
            sub_feats = x_prof[idx_tensor]
            sub_levels = t_levels[idx_tensor]
            sub_delta_l, sub_v = self.tier2_profession.forward_batch(p_name, sub_feats, sub_levels)
            delta_l_prof.index_copy_(0, idx_tensor, sub_delta_l)
            v_prof_total.index_copy_(0, idx_tensor, sub_v)

        # 3. Tier 3 BatchedAgentSelfNet (Individuality Slab)
        delta_l_self = torch.zeros((N, 20), dtype=torch.float32, device=self.device)
        x_self = x_living[:, :20]
        out_heads, _ = self.tier3_self(x_self, slot_indices)
        delta_l_self = out_heads[:, :20]

        # 4. Survival Gate g_survival
        if health_ratios is not None and hungers is not None:
            critical_mask = (health_ratios < 0.25) | (hungers < 15.0)
            g_survival = torch.where(
                critical_mask.unsqueeze(-1),
                0.25,
                1.0,
            )
        else:
            g_survival = 1.0

        # 5. Personality & Mood Bias Vector (Vectorized Matrix Multiplication)
        if isinstance(personalities, torch.Tensor) and personalities.shape[-1] == 15:
            t_bias = torch.matmul(personalities, self.bias_weight_matrix)
        else:
            raw_matrix = np.zeros((N, 15), dtype=np.float32)
            for i in range(N):
                p = personalities[i] if isinstance(personalities, list) else None
                if p is not None:
                    raw_matrix[i, 0] = p.courage
                    raw_matrix[i, 1] = p.empathy
                    raw_matrix[i, 2] = p.ambition
                    raw_matrix[i, 3] = p.discipline
                    raw_matrix[i, 4] = p.curiosity
                    raw_matrix[i, 5] = p.devotion
                    raw_matrix[i, 6] = p.honesty
                    raw_matrix[i, 7] = p.out_group_trust
                    raw_matrix[i, 8] = p.caution
                    raw_matrix[i, 9] = p.pride
                m = moods[i] if isinstance(moods, list) else None
                if m is not None:
                    raw_matrix[i, 10] = m.calm
                    raw_matrix[i, 11] = m.angry
                    raw_matrix[i, 12] = m.grieving
                    raw_matrix[i, 13] = m.fearful
                    raw_matrix[i, 14] = m.inspired
            pers_tensor = torch.from_numpy(raw_matrix).to(self.device)
            t_bias = torch.matmul(pers_tensor, self.bias_weight_matrix)

        # 6. Blending Formula:
        # L = L_living + 0.8 * tanh(Delta_prof) + 1.25 * tanh(Delta_self) * g_survival + Bias
        l_blended = (
            l_living
            + 0.8 * torch.tanh(delta_l_prof)
            + ALPHA_MOD * torch.tanh(delta_l_self) * g_survival
            + t_bias
        )

        # 7. Life-Stage Action Masking
        if isinstance(stages, torch.Tensor):
            stage_tensor = stages.to(device=self.device, dtype=torch.long)
        else:
            first_stg = stages[0] if stages else "ADULT"
            if all(s == first_stg for s in stages):
                idx = STAGE_NAME_TO_IDX.get(first_stg, 2)
                stage_tensor = torch.full((N,), idx, dtype=torch.long, device=self.device)
            else:
                stage_idx_list = [STAGE_NAME_TO_IDX.get(stg, 2) for stg in stages]
                stage_tensor = torch.as_tensor(stage_idx_list, dtype=torch.long, device=self.device)

        masks = self.stage_masks[stage_tensor]
        masked_logits = torch.where(masks, l_blended, -1e9)

        # 8. NaN Guard / Self-Healing
        if not torch.isfinite(masked_logits).all():
            if self.healer:
                self.healer.handle(
                    fault_class="TENSOR_NAN_INF",
                    day=0,
                    tick=0,
                    context={"msg": "NaN detected in hierarchical brain forward pass"},
                )
            masked_logits = torch.nan_to_num(masked_logits, nan=0.0, posinf=1.0, neginf=-1e9)

        values = v_living + 0.5 * v_prof_total
        return masked_logits, values

    def forward_agents(self, agents: list[Any]) -> tuple[torch.Tensor, torch.Tensor]:
        """Convenience caller accepting a list of AgentRecords or duck-typed objects."""
        N = len(agents)
        if N == 0:
            return torch.empty((0, 20), device=self.device), torch.empty((0, 1), device=self.device)

        slot_indices = [
            s if s is not None else 0 for s in (getattr(a, "slot_idx", 0) for a in agents)
        ]
        x_living = torch.zeros((N, 24), dtype=torch.float32, device=self.device)
        for i, a in enumerate(agents):
            x_living[i, 0] = a.health / max(1.0, getattr(a, "max_health", 40.0))
            x_living[i, 1] = a.hunger / 100.0
            x_living[i, 2] = a.stamina / 100.0
            x_living[i, 3] = getattr(a, "distress", 0.0)
            x_living[i, 4] = 1.0 if getattr(a, "crying", False) else 0.0
            x_living[i, 5] = getattr(a, "credits", 0.0) / 100.0
            x_living[i, 6] = getattr(a, "hygiene", 1.0)
            x_living[i, 7] = getattr(a, "fatigue", 0.0)

        professions = [getattr(a, "profession", "CITIZEN") for a in agents]
        levels = [getattr(a, "profession_level", 1) for a in agents]
        active_effects = [getattr(a, "active_mechanical_effects", {}) for a in agents]
        stages = [getattr(a, "stage", "ADULT") for a in agents]
        personalities = [getattr(a, "personality", None) for a in agents]
        moods = [getattr(a, "mood", None) for a in agents]
        health_ratios = torch.tensor(
            [a.health / max(1.0, getattr(a, "max_health", 40.0)) for a in agents],
            dtype=torch.float32,
            device=self.device,
        )
        hungers = torch.tensor([a.hunger for a in agents], dtype=torch.float32, device=self.device)

        return self.forward_batch(
            slot_indices=slot_indices,
            x_living=x_living,
            professions=professions,
            levels=levels,
            active_effects=active_effects,
            stages=stages,
            personalities=personalities,
            moods=moods,
            health_ratios=health_ratios,
            hungers=hungers,
        )
