"""
sim_core/brains/shared_living_net.py
Pillar 1 (Tier 1): Universal Shared Living Net.
Single shared batched PyTorch MLP governing everyday baseline living for ALL living agents:
- Walking / steering
- Eating / drinking
- Morning hygiene / grooming / brushing
- Sleeping / fatigue recovery
- Shelter-seeking in rain/snow/ash
- Personal-space avoidance
- Reflex danger evasion
Embeds intrinsic biological reward priors so agents never start as helpless blank slates.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

NUM_LIVING_INPUTS = 24
NUM_LIVING_ACTIONS = 20


class SharedLivingNet(nn.Module):
    """
    Tier 1 Universal Living Net evaluated across batches of agents:
    Architecture:
      Linear(24, 64) -> LayerNorm(64) -> SiLU()
      Linear(64, 64) -> LayerNorm(64) -> SiLU()
      Policy Head: Linear(64, 20) -> L_living
      Value Head:  Linear(64, 1)  -> V_living(s)
      Intrinsic Prior Head: Linear(64, 5) -> [hunger, shelter, hygiene, rest, curiosity]
    """

    def __init__(
        self,
        input_dim: int = NUM_LIVING_INPUTS,
        action_dim: int = NUM_LIVING_ACTIONS,
    ) -> None:
        super().__init__()
        self.input_dim = input_dim
        self.action_dim = action_dim

        self.fc1 = nn.Linear(input_dim, 64)
        self.ln1 = nn.LayerNorm(64)
        self.fc2 = nn.Linear(64, 64)
        self.ln2 = nn.LayerNorm(64)

        self.policy_head = nn.Linear(64, action_dim)
        self.value_head = nn.Linear(64, 1)
        self.intrinsic_head = nn.Linear(64, 5)

        # Initialize with biologically grounded priors
        self._init_living_priors()

    def _init_living_priors(self) -> None:
        """Sets positive heuristic weights on survival reflex pathways."""
        with torch.no_grad():
            nn.init.orthogonal_(self.fc1.weight, gain=1.0)
            nn.init.orthogonal_(self.fc2.weight, gain=1.0)
            nn.init.xavier_uniform_(self.policy_head.weight, gain=0.5)
            # Biased positive value for resting and eating
            self.policy_head.bias.data[0] += 0.2  # Rest
            self.policy_head.bias.data[1] += 0.3  # Eat
            self.policy_head.bias.data[2] += 0.1  # Groom

    def forward(
        self,
        x_living: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Batched forward pass.
        Args:
            x_living: (N, 24) float32 tensor
        Returns:
            l_living: (N, 20) baseline living action logits
            v_living: (N, 1) baseline living value estimate
            intrinsic_rewards: (N, 5) intrinsic biological reward signals
        """
        h = F.silu(self.ln1(self.fc1(x_living)))
        h = F.silu(self.ln2(self.fc2(h)))

        l_living = self.policy_head(h)
        v_living = self.value_head(h)
        intrinsic_rewards = torch.sigmoid(self.intrinsic_head(h))
        return l_living, v_living, intrinsic_rewards

    @staticmethod
    def extract_living_features(
        health: float,
        max_health: float,
        hunger: float,
        stamina: float,
        hygiene: float,
        fatigue: float,
        weather_severity: float = 0.0,
        threat_distance: float = 100.0,
        distress: float = 0.0,
        crying: bool = False,
        shelter_distance: float = 50.0,
        social_density: float = 0.2,
        curiosity_drive: float = 0.5,
    ) -> list[float]:
        """Utility to pack an agent's live bodily metrics into a 24-dim feature vector."""
        feats = [0.0] * NUM_LIVING_INPUTS
        feats[0] = health / max(1.0, max_health)
        feats[1] = hunger / 100.0
        feats[2] = stamina / 100.0
        feats[3] = hygiene
        feats[4] = fatigue
        feats[5] = weather_severity
        feats[6] = 1.0 / max(1.0, threat_distance * 0.1)
        feats[7] = distress
        feats[8] = 1.0 if crying else 0.0
        feats[9] = 1.0 / max(1.0, shelter_distance * 0.1)
        feats[10] = social_density
        feats[11] = curiosity_drive
        # Normalization and auxiliary slots
        feats[12] = 1.0 if hunger < 25.0 else 0.0  # Starvation alert
        feats[13] = 1.0 if fatigue > 0.8 else 0.0  # Exhaustion alert
        feats[14] = 1.0 if hygiene < 0.2 else 0.0  # Squalor alert
        feats[15] = 1.0 if weather_severity > 0.6 else 0.0  # Storm exposure
        return feats
