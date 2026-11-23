"""
sim_core/neural/shared_net.py
Species-wide SharedSkillNet providing physical, caregiving, economic, and social competence
over 20 embodied/macro primitives + state-value estimate V(s).
Follows NEURAL_AND_LIFECYCLE_SPEC.md Sections 1.1 & 1.3.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

NUM_SHARED_INPUTS = 32
NUM_ACTIONS = 20
ALPHA_MOD = 1.25
SURVIVAL_GATE_CLAMP = 0.25

# Hard Stage Mask: shape (4, 20)
# Stage 0 (INFANT): 0..5 unlocked, 6..19 locked
# Stage 1 (CHILD): 0..9 unlocked, 10..19 locked
# Stage 2 (ADULT): 0..19 unlocked
# Stage 3 (ELDER): 0..19 unlocked
STAGE_MASK_TENSOR = torch.zeros((4, NUM_ACTIONS), dtype=torch.bool)
STAGE_MASK_TENSOR[0, 0:6] = True
STAGE_MASK_TENSOR[1, 0:10] = True
STAGE_MASK_TENSOR[2, :] = True
STAGE_MASK_TENSOR[3, :] = True

STAGE_NAME_TO_IDX: dict[str, int] = {
    "INFANT": 0,
    "CHILD": 1,
    "ADULT": 2,
    "ELDER": 3,
}


class SharedSkillNet(nn.Module):
    """
    Evaluated in a single batched forward pass across scheduled agents.
    Provides species-wide physical competence and baseline value estimation.
    Architecture:
      Linear(32, 64) -> LayerNorm(64) -> Tanh()
      Linear(64, 64) -> LayerNorm(64) -> Tanh()
      Policy Head: Linear(64, 20) -> L_shared
      Value Head:  Linear(64, 1)  -> V(s)
    """

    stage_masks: torch.Tensor

    def __init__(self, input_dim: int = NUM_SHARED_INPUTS, action_dim: int = NUM_ACTIONS) -> None:
        super().__init__()
        self.input_dim = input_dim
        self.action_dim = action_dim

        self.fc1 = nn.Linear(input_dim, 64)
        self.ln1 = nn.LayerNorm(64)
        self.fc2 = nn.Linear(64, 64)
        self.ln2 = nn.LayerNorm(64)

        self.policy_head = nn.Linear(64, action_dim)
        self.value_head = nn.Linear(64, 1)

        self.register_buffer("stage_masks", STAGE_MASK_TENSOR.clone())

    def forward(self, x_shared: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass for shared skills.
        Args:
            x_shared: Tensor of shape (N, 32)
        Returns:
            l_shared: (N, 20) baseline action logits
            v_s: (N, 1) state-value estimate
        """
        h = torch.tanh(self.ln1(self.fc1(x_shared)))
        h = torch.tanh(self.ln2(self.fc2(h)))
        l_shared = self.policy_head(h)
        v_s = self.value_head(h)
        return l_shared, v_s

    @staticmethod
    def compute_survival_gate(
        health_ratio: torch.Tensor,
        hunger: torch.Tensor,
    ) -> torch.Tensor:
        """
        Computes the vectorized survival gate g_survival in [0.25, 1.0].
        Clamped to 0.25 whenever health / max_health < 0.25 or hunger < 15.0.
        Args:
            health_ratio: (N, 1) or (N,) Tensor in [0, 1]
            hunger: (N, 1) or (N,) Tensor in [0, 100]
        Returns:
            g_survival: (N, 1) Tensor where endangered slots are clamped to 0.25.
        """
        if health_ratio.dim() == 1:
            health_ratio = health_ratio.unsqueeze(-1)
        if hunger.dim() == 1:
            hunger = hunger.unsqueeze(-1)

        critical_mask = (health_ratio < 0.25) | (hunger < 15.0)
        g_survival = torch.where(
            critical_mask,
            torch.tensor(SURVIVAL_GATE_CLAMP, dtype=health_ratio.dtype, device=health_ratio.device),
            torch.tensor(1.0, dtype=health_ratio.dtype, device=health_ratio.device),
        )
        return g_survival

    def blend_logits(
        self,
        l_shared: torch.Tensor,
        delta_l_self: torch.Tensor,
        g_survival: torch.Tensor,
        alpha_mod: float = ALPHA_MOD,
    ) -> torch.Tensor:
        """
        Competence-Preserving Blending:
        L_raw = L_shared + alpha_mod * tanh(delta_L_self) * g_survival
        Args:
            l_shared: (N, 20)
            delta_l_self: (N, 20)
            g_survival: (N, 1) or (N, 20)
            alpha_mod: float modifier (default 1.25)
        Returns:
            l_raw: (N, 20) blended action logits
        """
        return l_shared + alpha_mod * torch.tanh(delta_l_self) * g_survival

    def apply_stage_mask(
        self,
        l_raw: torch.Tensor,
        stage_indices: torch.Tensor,
    ) -> torch.Tensor:
        """
        Applies hard stage masking to locked primitives with -1e9.
        Args:
            l_raw: (N, 20) blended logits
            stage_indices: (N,) LongTensor with values in [0, 3]
        Returns:
            masked_logits: (N, 20) with locked actions replaced by -1e9
        """
        masks = self.stage_masks[stage_indices]  # (N, 20) boolean
        neg_inf = torch.tensor(-1e9, dtype=l_raw.dtype, device=l_raw.device)
        return torch.where(masks, l_raw, neg_inf)

    def compute_action_distribution(
        self,
        masked_logits: torch.Tensor,
        confidence: torch.Tensor | None = None,
    ) -> torch.distributions.Categorical:
        """
        Computes action categorical distribution with temperature scaling:
        tau = 1.2 - 0.5 * c_t
        Args:
            masked_logits: (N, 20)
            confidence: (N, 1) or (N,) Tensor in (0, 1), optional (defaults to 0.5)
        Returns:
            Categorical distribution over 20 actions
        """
        if confidence is None:
            tau = torch.ones((masked_logits.shape[0], 1), device=masked_logits.device) * 0.95
        else:
            if confidence.dim() == 1:
                confidence = confidence.unsqueeze(-1)
            tau = torch.clamp(1.2 - 0.5 * confidence, min=0.1, max=2.0)

        scaled_logits = masked_logits / tau
        probs = F.softmax(scaled_logits, dim=-1)
        return torch.distributions.Categorical(probs=probs)
