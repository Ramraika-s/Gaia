"""
sim_core/neural/trainer.py
Vectorized rollout buffer (T = 32), stage-weighted intrinsic curiosity,
policy + value + self-prediction losses, per-slot neuroplasticity learning rates,
and batched backpropagation for SharedSkillNet and BatchedAgentSelfNet.
Follows NEURAL_AND_LIFECYCLE_SPEC.md Section 3.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from sim_core.neural.batched_self_net import BatchedAgentSelfNet
from sim_core.neural.shared_net import SharedSkillNet

ROLLOUT_STEPS_T = 32
DISCOUNT_GAMMA = 0.95
GLOBAL_GRAD_CLIP = 1.0

# Stage curiosity weights kappa(stage)
KAPPA_CURIOSITY = torch.tensor([0.05, 0.035, 0.01, 0.0], dtype=torch.float32)

# Base stage learning rates and entropy coefficients
STAGE_BASE_LR = torch.tensor([3.0e-3, 1.5e-3, 5.0e-4, 1.5e-4], dtype=torch.float32)
STAGE_ENTROPY_BETA = torch.tensor([0.025, 0.020, 0.008, 0.004], dtype=torch.float32)


class RolloutBuffer:
    """
    Pre-allocated RAM ring tensors for T = 32 steps across living agents.
    Maintains obs_shared, obs_self, actions, log_probs, values, rewards, stages.
    """

    def __init__(
        self,
        capacity: int,
        steps: int = ROLLOUT_STEPS_T,
        device: str | torch.device = "cpu",
    ) -> None:
        self.capacity = capacity
        self.steps = steps
        self.device = torch.device(device)
        self.step_idx = 0

        self.obs_shared = torch.zeros((steps, capacity, 32), device=self.device)
        self.obs_self = torch.zeros((steps, capacity, 20), device=self.device)
        self.actions = torch.zeros((steps, capacity), dtype=torch.long, device=self.device)
        self.log_probs = torch.zeros((steps, capacity), device=self.device)
        self.values = torch.zeros((steps, capacity), device=self.device)
        self.rewards_ext = torch.zeros((steps, capacity), device=self.device)
        self.rewards_pred = torch.zeros((steps, capacity), device=self.device)
        self.confidences = torch.zeros((steps, capacity), device=self.device)
        self.stages = torch.zeros((steps, capacity), dtype=torch.long, device=self.device)
        self.dones = torch.zeros((steps, capacity), dtype=torch.bool, device=self.device)
        self.active_masks = torch.zeros((steps, capacity), dtype=torch.bool, device=self.device)

    def insert(
        self,
        slot_indices: torch.Tensor,
        obs_shared: torch.Tensor,
        obs_self: torch.Tensor,
        action: torch.Tensor,
        log_prob: torch.Tensor,
        value: torch.Tensor,
        reward_ext: torch.Tensor,
        reward_pred: torch.Tensor,
        confidence: torch.Tensor,
        stage: torch.Tensor,
        done: torch.Tensor,
    ) -> None:
        """Inserts one transition for active slot indices at current step_idx."""
        t = self.step_idx % self.steps

        self.obs_shared[t, slot_indices] = obs_shared.detach()
        self.obs_self[t, slot_indices] = obs_self.detach()
        self.actions[t, slot_indices] = action.detach()
        self.log_probs[t, slot_indices] = log_prob.detach()
        self.values[t, slot_indices] = value.squeeze(-1).detach()
        self.rewards_ext[t, slot_indices] = reward_ext.squeeze(-1).detach()
        self.rewards_pred[t, slot_indices] = reward_pred.squeeze(-1).detach()
        self.confidences[t, slot_indices] = confidence.squeeze(-1).detach()
        self.stages[t, slot_indices] = stage.detach()
        self.dones[t, slot_indices] = done.detach()
        self.active_masks[t, slot_indices] = True

        self.step_idx += 1

    @property
    def is_full(self) -> bool:
        return self.step_idx >= self.steps

    def reset(self) -> None:
        self.step_idx = 0
        self.active_masks.zero_()


class BatchedNeuralTrainer:
    """
    Coordinates policy gradient, value learning, self-prediction loss,
    and stage-weighted curiosity updates for SharedSkillNet and BatchedAgentSelfNet.
    """

    def __init__(
        self,
        shared_net: SharedSkillNet,
        self_net: BatchedAgentSelfNet,
        gamma: float = DISCOUNT_GAMMA,
        device: str | torch.device = "cpu",
    ) -> None:
        self.shared_net = shared_net
        self.self_net = self_net
        self.gamma = gamma
        self.device = torch.device(device)

        self.shared_optimizer = torch.optim.Adam(self.shared_net.parameters(), lr=3.0e-4)

    @staticmethod
    def compute_curiosity_bonus(
        r_ext: torch.Tensor,
        r_pred: torch.Tensor,
        stages: torch.Tensor,
    ) -> torch.Tensor:
        """
        Computes stage-weighted intrinsic curiosity:
        e_t = r_ext - r_pred
        r_cur = kappa(stage) * min(|e_t|, 1.5)
        """
        err = torch.abs(r_ext - r_pred)
        capped_err = torch.clamp(err, max=1.5)
        kappa = KAPPA_CURIOSITY.to(r_ext.device)[stages]
        return kappa * capped_err

    def compute_returns_and_advantages(
        self,
        rewards: torch.Tensor,
        values: torch.Tensor,
        dones: torch.Tensor,
        active_masks: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Computes discounted returns G_t and advantages A_t = G_t - V(s_t) backwards in time.
        Args:
            rewards: (T, C)
            values: (T, C)
            dones: (T, C)
            active_masks: (T, C)
        Returns:
            returns: (T, C)
            advantages: (T, C)
        """
        t_steps, capacity = rewards.shape
        returns = torch.zeros_like(rewards)
        running_returns = torch.zeros(capacity, device=self.device)

        for t in reversed(range(t_steps)):
            not_done = (~dones[t]).float()
            running_returns = rewards[t] + self.gamma * running_returns * not_done
            returns[t] = running_returns

        advantages = returns - values
        return returns, advantages

    def train_step(
        self,
        buffer: RolloutBuffer,
        active_slots: torch.Tensor,
        neuroplasticity_mults: torch.Tensor | None = None,
    ) -> dict[str, float]:
        """
        Executes one batched training update over collected buffer transitions.
        Args:
            buffer: RolloutBuffer holding T = 32 steps
            active_slots: (N,) LongTensor of active slots to optimize
            neuroplasticity_mults: (N,) Tensor of race neuroplasticity multipliers
        Returns:
            metrics dictionary with losses
        """
        if neuroplasticity_mults is None:
            neuroplasticity_mults = torch.ones(
                active_slots.shape[0], dtype=torch.float32, device=self.device
            )

        t_steps = min(buffer.step_idx, buffer.steps)
        if t_steps < 2 or active_slots.numel() == 0:
            buffer.reset()
            return {"loss_total": 0.0, "loss_policy": 0.0, "loss_value": 0.0, "loss_pred": 0.0}

        # 1. Total Rewards = Extrinsic + Stage-Weighted Curiosity
        r_ext = buffer.rewards_ext[:t_steps, active_slots]
        r_pred = buffer.rewards_pred[:t_steps, active_slots]
        stg = buffer.stages[:t_steps, active_slots]
        r_cur = self.compute_curiosity_bonus(r_ext, r_pred, stg)
        r_total = r_ext + r_cur

        vals = buffer.values[:t_steps, active_slots]
        dns = buffer.dones[:t_steps, active_slots]
        act_mask = buffer.active_masks[:t_steps, active_slots]

        # 2. Vectorized returns and advantages
        returns, advantages = self.compute_returns_and_advantages(r_total, vals, dns, act_mask)

        # 3. Flatten batch over active slots
        flat_mask = act_mask.view(-1)
        if not flat_mask.any():
            buffer.reset()
            return {"loss_total": 0.0, "loss_policy": 0.0, "loss_value": 0.0, "loss_pred": 0.0}

        flat_obs_shared = buffer.obs_shared[:t_steps, active_slots].view(-1, 32)[flat_mask]
        flat_obs_self = buffer.obs_self[:t_steps, active_slots].view(-1, 20)[flat_mask]
        flat_actions = buffer.actions[:t_steps, active_slots].view(-1)[flat_mask]
        flat_returns = returns.view(-1)[flat_mask]
        flat_advantages = advantages.view(-1)[flat_mask]
        flat_stages = stg.view(-1)[flat_mask]
        flat_r_ext = r_ext.view(-1)[flat_mask]

        # Repeated slot indices for flattened tensor
        repeated_slots = active_slots.repeat(t_steps)[flat_mask]

        # 4. Forward pass through SharedSkillNet & BatchedAgentSelfNet
        l_shared, v_pred = self.shared_net(flat_obs_shared)
        out_self, _ = self.self_net(flat_obs_self, slot_indices=repeated_slots)

        delta_l_self = out_self[:, 0:20]
        r_self_pred = out_self[:, 20:21].squeeze(-1)
        conf_logits = out_self[:, 21:22]
        confidence = torch.sigmoid(conf_logits)

        # Competence-preserving blending & stage masking
        health_ratio = flat_obs_shared[:, 0]
        hunger = flat_obs_shared[:, 1] * 100.0
        g_survival = SharedSkillNet.compute_survival_gate(health_ratio, hunger)
        l_raw = self.shared_net.blend_logits(l_shared, delta_l_self, g_survival)
        masked_logits = self.shared_net.apply_stage_mask(l_raw, flat_stages)

        dist = self.shared_net.compute_action_distribution(masked_logits, confidence)
        new_log_probs = dist.log_prob(flat_actions)
        entropy = dist.entropy()

        # 5. Losses
        # Policy loss with stage-based entropy bonus
        ent_beta = STAGE_ENTROPY_BETA.to(self.device)[flat_stages]
        policy_loss = -torch.mean(new_log_probs * flat_advantages.detach()) - torch.mean(
            ent_beta * entropy
        )

        # Value loss (SharedSkillNet)
        value_loss = F.mse_loss(v_pred.squeeze(-1), flat_returns)

        # Self-prediction loss (BatchedAgentSelfNet)
        pred_loss = F.mse_loss(r_self_pred, flat_r_ext)

        total_loss = policy_loss + 0.5 * value_loss + pred_loss

        # 6. Optimization
        self.shared_optimizer.zero_grad()
        if self.self_net.W_ih.grad is not None:
            self.self_net.zero_grad()

        total_loss.backward()

        # Global gradient clipping
        nn.utils.clip_grad_norm_(self.shared_net.parameters(), GLOBAL_GRAD_CLIP)
        for param in (
            self.self_net.W_ih,
            self.self_net.b_ih,
            self.self_net.W_hh,
            self.self_net.b_hh,
            self.self_net.W_out,
            self.self_net.b_out,
        ):
            if param.grad is not None:
                nn.utils.clip_grad_norm_(param, GLOBAL_GRAD_CLIP)

        self.shared_optimizer.step()

        # Apply per-slot stage and race-scaled learning rates to BatchedAgentSelfNet
        with torch.no_grad():
            stage_lr_table = STAGE_BASE_LR.to(self.device)
            # Compute effective learning rate per active slot
            # (N,) Tensor
            base_lrs = stage_lr_table[buffer.stages[0, active_slots]]
            effective_lrs = base_lrs * neuroplasticity_mults

            for param in (
                self.self_net.W_ih,
                self.self_net.b_ih,
                self.self_net.W_hh,
                self.self_net.b_hh,
                self.self_net.W_out,
                self.self_net.b_out,
            ):
                if param.grad is not None:
                    # Update active slots scaled by their individual learning rate
                    # Expand lr for broadcasting: (N, 1, 1) or (N, 1)
                    lr_view = effective_lrs.view(-1, *([1] * (param.ndim - 1)))
                    param.data[active_slots] -= lr_view * param.grad.data[active_slots]

        buffer.reset()

        return {
            "loss_total": float(total_loss.item()),
            "loss_policy": float(policy_loss.item()),
            "loss_value": float(value_loss.item()),
            "loss_pred": float(pred_loss.item()),
        }
