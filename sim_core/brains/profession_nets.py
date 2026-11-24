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
from collections.abc import Mapping
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

# Canonical mechanical effect key sets mapped to 6 profession feature channels
CHANNEL_0_KEYS: frozenset[str] = frozenset(
    {
        "defense",
        "defense_bonus",
        "combat_power_multiplier",
        "patrol_efficiency",
        "structural_integrity_bonus",
    }
)
CHANNEL_1_KEYS: frozenset[str] = frozenset(
    {
        "yield_mult",
        "craft_speed_bonus",
        "smelting_yield_bonus",
        "tool_durability_bonus",
        "crop_yield_bonus",
        "spoilage_reduction",
        "construction_cost_reduction",
    }
)
CHANNEL_2_KEYS: frozenset[str] = frozenset(
    {
        "trade_margin",
        "trade_fee_reduction",
        "market_clearing_efficiency",
        "credit_default_reduction",
    }
)
CHANNEL_3_KEYS: frozenset[str] = frozenset(
    {"research_rate", "judicial_accuracy", "civil_stability_bonus", "reputation_bonus"}
)
CHANNEL_4_KEYS: frozenset[str] = frozenset(
    {"faith_gain", "faith_devotion_bonus", "divine_favor_generation"}
)
CHANNEL_5_KEYS: frozenset[str] = frozenset(
    {
        "stamina_efficiency",
        "winter_hardiness",
        "healing_rate_bonus",
        "infection_resistance",
        "fertility_rate_bonus",
        "attrition_reduction",
    }
)

# Flat O(1) key-to-channel mapping for fast vectorized feature aggregation
EFFECT_KEY_TO_CHANNEL: dict[str, int] = {}
for _k in CHANNEL_0_KEYS:
    EFFECT_KEY_TO_CHANNEL[_k] = 0
for _k in CHANNEL_1_KEYS:
    EFFECT_KEY_TO_CHANNEL[_k] = 1
for _k in CHANNEL_2_KEYS:
    EFFECT_KEY_TO_CHANNEL[_k] = 2
for _k in CHANNEL_3_KEYS:
    EFFECT_KEY_TO_CHANNEL[_k] = 3
for _k in CHANNEL_4_KEYS:
    EFFECT_KEY_TO_CHANNEL[_k] = 4
for _k in CHANNEL_5_KEYS:
    EFFECT_KEY_TO_CHANNEL[_k] = 5


def aggregate_effect_channels(
    active_effects: dict[str, float] | Mapping[str, float],
) -> tuple[float, float, float, float, float, float]:
    """
    Aggregates active mechanical effect bonuses into 6 normalized channels in [-1.0, 1.0].
    Maps legacy short keys and all canonical MECHANICAL_EFFECT_BOUNDS keys:
      Channel 0: defense
      Channel 1: yield_mult
      Channel 2: trade_margin
      Channel 3: research_rate
      Channel 4: faith_gain
      Channel 5: stamina_efficiency
    """
    ch = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    for k, v in active_effects.items():
        idx = EFFECT_KEY_TO_CHANNEL.get(k)
        if idx is not None:
            ch[idx] += v

    return (
        max(-1.0, min(1.0, ch[0])),
        max(-1.0, min(1.0, ch[1])),
        max(-1.0, min(1.0, ch[2])),
        max(-1.0, min(1.0, ch[3])),
        max(-1.0, min(1.0, ch[4])),
        max(-1.0, min(1.0, ch[5])),
    )


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
        c0, c1, c2, c3, c4, c5 = aggregate_effect_channels(active_mechanical_effects)
        feats.append(float(level) / 10.0)  # Slot 20: level
        feats.append(min(1.0, xp / 1000.0))  # Slot 21: normalized XP
        feats.append(c0)  # Slot 22: defense buff
        feats.append(c1)  # Slot 23: harvest/craft buff
        feats.append(c2)  # Slot 24: commerce buff
        feats.append(c3)  # Slot 25: scholarship buff
        feats.append(c4)  # Slot 26: devotion buff
        feats.append(c5)  # Slot 27: endurance buff
        return feats
