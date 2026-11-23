"""
sim_core/brains/profession_nets.py
Pillar 1 (Tier 2): Grouped Profession Nets (Lv. 1–10) & Registry.
Maintains one shared batched MLP per profession:
- KNIGHT, CITY_GUARD, FARMER, MERCHANT, BLACKSMITH, BUILDER, SCHOLAR, CLERIC, HUNTER, CITIZEN.
Batches agents by profession so thousands of agents share compact weights while scaling
capability by profession_level (Lv. 1–10) and XP progression.
Applies unlocked world_library mechanical_effects strictly from books the agent has read.
"""

from __future__ import annotations

import copy
from typing import Any

import torch
import torch.nn as nn

PROFESSION_INPUT_DIM = 28
NUM_ACTIONS = 20

PROFESSIONS = [
    "KNIGHT",
    "CITY_GUARD",
    "FARMER",
    "MERCHANT",
    "BLACKSMITH",
    "BUILDER",
    "SCHOLAR",
    "CLERIC",
    "HUNTER",
    "CITIZEN",
]


class ProfessionNet(nn.Module):
    """
    Compact batched MLP for a specific profession.
    Scaled by agent's profession_level (1 to 10) and mechanical effects.
    """

    def __init__(
        self,
        input_dim: int = PROFESSION_INPUT_DIM,
        action_dim: int = NUM_ACTIONS,
    ) -> None:
        super().__init__()
        self.input_dim = input_dim
        self.action_dim = action_dim

        self.net = nn.Sequential(
            nn.Linear(input_dim, 48),
            nn.LayerNorm(48),
            nn.SiLU(),
            nn.Linear(48, 48),
            nn.SiLU(),
            nn.Linear(48, action_dim),
        )
        self.value_head = nn.Linear(48, 1)

    def forward(
        self,
        x: torch.Tensor,
        levels: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass for a batch of agents sharing this profession.
        Args:
            x: (N, 28) features
            levels: (N, 1) profession level in [1.0, 10.0]
        Returns:
            delta_l: (N, 20) action delta logits scaled by level
            v_prof: (N, 1) profession value estimate
        """
        h = self.net[0](x)
        h = self.net[1](h)
        h = self.net[2](h)
        h = self.net[3](h)
        h = self.net[4](h)

        raw_delta = self.net[5](h)
        v_prof = self.value_head(h)

        # Scale capability by level: Lv 1 -> 0.6x, Lv 5 -> 1.0x, Lv 10 -> 1.5x
        level_scale = 0.5 + (levels / 10.0)
        delta_l = raw_delta * level_scale
        return delta_l, v_prof


class ProfessionNetRegistry:
    """
    Registry of all 10 profession networks.
    Provides batch grouping, forward routing, and checkpoint/rollback for sleep distillation.
    """

    def __init__(self, device: str | torch.device = "cpu") -> None:
        self.device = torch.device(device)
        self.nets: dict[str, ProfessionNet] = {}
        for p in PROFESSIONS:
            self.nets[p] = ProfessionNet().to(self.device)

        # Snapshots for stability-gated rollback during distillation
        self.backup_weights: dict[str, dict[str, Any]] = {}

    def get_net(self, profession: str) -> ProfessionNet:
        prof = profession.upper()
        if prof not in self.nets:
            prof = "CITIZEN"
        return self.nets[prof]

    def forward_batch(
        self,
        profession: str,
        x_features: torch.Tensor,
        levels: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Evaluates batch for a specific profession."""
        net = self.get_net(profession)
        return net(x_features, levels)

    def snapshot_weights(self, profession: str) -> None:
        """Stores a clean backup before applying distillation gradients."""
        prof = profession.upper()
        net = self.get_net(prof)
        self.backup_weights[prof] = copy.deepcopy(net.state_dict())

    def rollback_weights(self, profession: str) -> None:
        """Restores clean backup if validation loss regresses or NaN detected."""
        prof = profession.upper()
        if prof in self.backup_weights:
            self.nets[prof].load_state_dict(self.backup_weights[prof])

    @staticmethod
    def pack_profession_features(
        base_living_features: list[float],
        level: int,
        xp: float,
        active_mechanical_effects: dict[str, float],
    ) -> list[float]:
        """
        Packs living features + level + XP + active world_library effects into 28-dim vector.
        Information asymmetry: Only books the agent has read appear in active_mechanical_effects.
        """
        feats = list(base_living_features[:20])
        # Pad to 20 if living features was smaller
        while len(feats) < 20:
            feats.append(0.0)

        # Slots 20..27:
        eff = active_mechanical_effects
        feats.append(float(level) / 10.0)  # Slot 20: level
        feats.append(min(1.0, xp / 1000.0))  # Slot 21: normalized XP
        feats.append(eff.get("defense", 0.0))  # Slot 22: defense buff
        feats.append(eff.get("yield_mult", 0.0))  # Slot 23: harvest/craft buff
        feats.append(eff.get("trade_margin", 0.0))  # Slot 24: commerce buff
        feats.append(eff.get("research_rate", 0.0))  # Slot 25: scholarship buff
        feats.append(eff.get("faith_gain", 0.0))  # Slot 26: devotion buff
        feats.append(eff.get("stamina_efficiency", 0.0))  # Slot 27: endurance buff
        return feats
