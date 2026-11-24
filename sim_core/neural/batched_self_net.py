"""
sim_core/neural/batched_self_net.py
Unbounded 2,048-slot slab-grown BatchedAgentSelfNet with GRUCell(20, 32) working memory,
single-call torch.bmm forward math, free-slot pool, genetic crossover & mutation,
and torch.isfinite self-healing tensor guard.
Follows NEURAL_AND_LIFECYCLE_SPEC.md Section 1.2.
"""

from __future__ import annotations

import math
from typing import Any

import torch
import torch.nn as nn

from sim_core.config import SLAB_SIZE
from sim_core.resilience.healer import ErrorHealer

NUM_SELF_INPUTS = 20
HIDDEN_DIM = 32
GRU_GATES = 3  # reset, update, candidate
NUM_OUTPUT_HEADS = 22  # 20 delta_L, 1 predicted_reward, 1 confidence_logit


class BatchedAgentSelfNet(nn.Module):
    """
    Contiguous 3D slab-grown parameter tensors for unbounded neural agents.
    Parameters per slot i in [0, C):
      W_ih: (C, 20, 96), b_ih: (C, 96)
      W_hh: (C, 32, 96), b_hh: (C, 96)
      W_out: (C, 32, 22), b_out: (C, 22)
      H: (C, 32) persistent working memory hidden state
    Evaluates N scheduled agents in a single torch.bmm call without Python for-loops.
    """

    def __init__(
        self,
        initial_capacity: int = SLAB_SIZE,
        slab_size: int = SLAB_SIZE,
        device: str | torch.device = "cpu",
        healer: ErrorHealer | None = None,
    ) -> None:
        super().__init__()
        self.device = torch.device(device)
        self.slab_size = slab_size
        self.capacity = initial_capacity
        self.healer = healer

        # Free slot pool (tracks available slot indices)
        self.free_slots: list[int] = list(range(initial_capacity - 1, -1, -1))
        self.active_slots: set[int] = set()

        # Initialize parameter tensors
        gru_hidden_x3 = HIDDEN_DIM * GRU_GATES
        self.W_ih = nn.Parameter(
            self._init_weight(initial_capacity, NUM_SELF_INPUTS, gru_hidden_x3)
        )
        self.b_ih = nn.Parameter(torch.zeros((initial_capacity, gru_hidden_x3), device=self.device))
        self.W_hh = nn.Parameter(self._init_weight(initial_capacity, HIDDEN_DIM, gru_hidden_x3))
        self.b_hh = nn.Parameter(torch.zeros((initial_capacity, gru_hidden_x3), device=self.device))

        self.W_out = nn.Parameter(self._init_weight(initial_capacity, HIDDEN_DIM, NUM_OUTPUT_HEADS))
        self.b_out = nn.Parameter(
            torch.zeros((initial_capacity, NUM_OUTPUT_HEADS), device=self.device)
        )

        # Persistent hidden states (not parameters with gradients, but persistent state)
        self.register_buffer("H", torch.zeros((initial_capacity, HIDDEN_DIM), device=self.device))

    def _init_weight(self, c: int, in_features: int, out_features: int) -> torch.Tensor:
        """Kaiming uniform initialization for batched weights (c, in, out)."""
        w = torch.empty((c, in_features, out_features), device=self.device)
        bound = 1.0 / math.sqrt(in_features) if in_features > 0 else 0.1
        w.uniform_(-bound, bound)
        return w

    def grow_capacity(self, num_slabs: int = 1) -> int:
        """
        Dynamically allocates new slabs of 2,048 slots via torch.cat.
        Preserves all existing agent weights and persistent hidden states.
        Returns the new total capacity.
        """
        added_slots = num_slabs * self.slab_size
        old_capacity = self.capacity
        new_capacity = old_capacity + added_slots

        new_w_ih = self._init_weight(added_slots, NUM_SELF_INPUTS, HIDDEN_DIM * GRU_GATES)
        new_b_ih = torch.zeros((added_slots, HIDDEN_DIM * GRU_GATES), device=self.device)
        new_w_hh = self._init_weight(added_slots, HIDDEN_DIM, HIDDEN_DIM * GRU_GATES)
        new_b_hh = torch.zeros((added_slots, HIDDEN_DIM * GRU_GATES), device=self.device)
        new_w_out = self._init_weight(added_slots, HIDDEN_DIM, NUM_OUTPUT_HEADS)
        new_b_out = torch.zeros((added_slots, NUM_OUTPUT_HEADS), device=self.device)
        new_h = torch.zeros((added_slots, HIDDEN_DIM), device=self.device)

        with torch.no_grad():
            self.W_ih = nn.Parameter(torch.cat([self.W_ih.data, new_w_ih], dim=0))
            self.b_ih = nn.Parameter(torch.cat([self.b_ih.data, new_b_ih], dim=0))
            self.W_hh = nn.Parameter(torch.cat([self.W_hh.data, new_w_hh], dim=0))
            self.b_hh = nn.Parameter(torch.cat([self.b_hh.data, new_b_hh], dim=0))
            self.W_out = nn.Parameter(torch.cat([self.W_out.data, new_w_out], dim=0))
            self.b_out = nn.Parameter(torch.cat([self.b_out.data, new_b_out], dim=0))
            self.H = torch.cat([self.H, new_h], dim=0)

        # Add new slots to free pool (prepended in descending order so lower indices pop first)
        new_slots = list(range(new_capacity - 1, old_capacity - 1, -1))
        self.free_slots = new_slots + self.free_slots

        self.capacity = new_capacity
        return new_capacity

    def allocate_slot(
        self,
        parent1_slot: int | None = None,
        parent2_slot: int | None = None,
        mutation_std: float = 0.03,
    ) -> int:
        """
        Allocates a slot index for an agent.
        If parent slots are specified: performs Bernoulli(0.5) crossover + Gaussian mutation.
        Hidden state H is strictly zeroed on birth.
        """
        if not self.free_slots:
            self.grow_capacity(num_slabs=1)

        slot = self.free_slots.pop()
        self.active_slots.add(slot)

        with torch.no_grad():
            if parent1_slot is not None and parent2_slot is not None:
                # Bernoulli(0.5) Crossover + Gaussian Mutation
                for param in (self.W_ih, self.b_ih, self.W_hh, self.b_hh, self.W_out, self.b_out):
                    p1 = param.data[parent1_slot]
                    p2 = param.data[parent2_slot]
                    mask = torch.rand_like(p1) < 0.5
                    child_p = torch.where(mask, p1, p2)
                    if mutation_std > 0.0:
                        child_p = child_p + torch.randn_like(child_p) * mutation_std
                    param.data[slot].copy_(child_p)
            else:
                # Fresh random individual
                bound_ih = 1.0 / math.sqrt(NUM_SELF_INPUTS)
                self.W_ih.data[slot].uniform_(-bound_ih, bound_ih)
                self.b_ih.data[slot].zero_()
                bound_hh = 1.0 / math.sqrt(HIDDEN_DIM)
                self.W_hh.data[slot].uniform_(-bound_hh, bound_hh)
                self.b_hh.data[slot].zero_()
                self.W_out.data[slot].uniform_(-bound_hh, bound_hh)
                self.b_out.data[slot].zero_()

            # Hidden state is strictly zeroed on birth
            self.H[slot].zero_()

        return slot

    def free_slot(self, slot: int) -> None:
        """Reclaims a slot on death. Hidden state is zeroed."""
        if slot in self.active_slots:
            self.active_slots.remove(slot)
            with torch.no_grad():
                self.H[slot].zero_()
            self.free_slots.append(slot)

    def forward(
        self,
        x_self: torch.Tensor,
        slot_indices: torch.Tensor | None = None,
        day: int = 1,
        tick: int = 0,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Single-call batched forward math (No Python loops over agents):
        Args:
            x_self: (N, 20)
            slot_indices: (N,) LongTensor indexing into [0, capacity)
            day: current simulation day (for Healer incident logging)
            tick: current simulation tick (for Healer incident logging)
        Returns:
            out: (N, 22) -> [:, 0:20] delta_L, [:, 20:21] r_pred, [:, 21:22] conf_logit
            h_next: (N, 32) updated hidden states
        """
        n = x_self.shape[0]
        use_slice = False
        start_idx = 0
        end_idx = n

        if slot_indices is None:
            use_slice = True
            start_idx = 0
            end_idx = n
        elif isinstance(slot_indices, (list, tuple)) and n > 0:
            first = int(slot_indices[0])
            last = int(slot_indices[-1])
            if n == 1 or (
                last - first == n - 1 and all(slot_indices[i] == first + i for i in range(n))
            ):
                use_slice = True
                start_idx = first
                end_idx = last + 1
        elif isinstance(slot_indices, torch.Tensor) and n > 0:
            first = int(slot_indices[0].item())
            last = int(slot_indices[-1].item())
            if n == 1 or bool((slot_indices[1:] == slot_indices[:-1] + 1).all()):
                use_slice = True
                start_idx = first
                end_idx = last + 1

        if use_slice:
            # Zero-copy view: avoids copying hundreds of megabytes on every tick
            w_ih = self.W_ih[start_idx:end_idx]
            b_ih = self.b_ih[start_idx:end_idx]
            w_hh = self.W_hh[start_idx:end_idx]
            b_hh = self.b_hh[start_idx:end_idx]
            w_out = self.W_out[start_idx:end_idx]
            b_out = self.b_out[start_idx:end_idx]
            h_prev = self.H[start_idx:end_idx]
        else:
            if isinstance(slot_indices, (list, tuple)):
                idx_t = torch.as_tensor(slot_indices, dtype=torch.long, device=self.device)
            else:
                idx_t = slot_indices
            w_ih = self.W_ih[idx_t]
            b_ih = self.b_ih[idx_t]
            w_hh = self.W_hh[idx_t]
            b_hh = self.b_hh[idx_t]
            w_out = self.W_out[idx_t]
            b_out = self.b_out[idx_t]
            h_prev = self.H[idx_t]

        # Vectorized batch matrix multiplication
        gi = torch.bmm(x_self.unsqueeze(1), w_ih).squeeze(1) + b_ih  # (N, 96)
        gh = torch.bmm(h_prev.unsqueeze(1), w_hh).squeeze(1) + b_hh  # (N, 96)

        i_r, i_z, i_n = gi.chunk(3, dim=-1)
        h_r, h_z, h_n = gh.chunk(3, dim=-1)

        r = torch.sigmoid(i_r + h_r)
        z = torch.sigmoid(i_z + h_z)
        cand = torch.tanh(i_n + r * h_n)
        h_next = (1.0 - z) * cand + z * h_prev  # (N, 32)

        out = torch.bmm(h_next.unsqueeze(1), w_out).squeeze(1) + b_out  # (N, 22)

        # Check tensor integrity
        is_finite_out = torch.isfinite(out).all(dim=-1)
        is_finite_h = torch.isfinite(h_next).all(dim=-1)
        valid_mask = is_finite_out & is_finite_h

        if not valid_mask.all():
            bad_batch_indices = torch.nonzero(~valid_mask).squeeze(-1).tolist()
            if isinstance(bad_batch_indices, int):
                bad_batch_indices = [bad_batch_indices]

            for b_idx in bad_batch_indices:
                if use_slice or slot_indices is None:
                    bad_slot = start_idx + b_idx
                elif isinstance(slot_indices, torch.Tensor):
                    bad_slot = int(slot_indices[b_idx].item())
                else:
                    bad_slot = int(slot_indices[b_idx])

                # Restore corrupted slot locally
                with torch.no_grad():
                    self.H[bad_slot].zero_()
                    # Reset corrupted parameters
                    bound_ih = 1.0 / math.sqrt(NUM_SELF_INPUTS)
                    self.W_ih.data[bad_slot].uniform_(-bound_ih, bound_ih)
                    self.b_ih.data[bad_slot].zero_()
                    bound_hh = 1.0 / math.sqrt(HIDDEN_DIM)
                    self.W_hh.data[bad_slot].uniform_(-bound_hh, bound_hh)
                    self.b_hh.data[bad_slot].zero_()
                    self.W_out.data[bad_slot].uniform_(-bound_hh, bound_hh)
                    self.b_out.data[bad_slot].zero_()

                    # Clean outputs in returned batch
                    h_next.data[b_idx].zero_()
                    out.data[b_idx].zero_()

                # Report to ErrorHealer
                if self.healer is not None:
                    self.healer.handle(
                        fault_class="TENSOR_NAN_INF",
                        day=day,
                        tick=tick,
                        agent_id=f"slot_{bad_slot}",
                        context={"slot_idx": bad_slot},
                    )

        # Update persistent working memory for healthy slots
        if use_slice:
            self.H[start_idx:end_idx] = h_next.detach()
        elif isinstance(slot_indices, torch.Tensor):
            self.H[slot_indices] = h_next.detach()
        else:
            self.H[torch.as_tensor(slot_indices, dtype=torch.long, device=self.device)] = (
                h_next.detach()
            )

        return out, h_next

    def get_state_dict(self) -> dict[str, Any]:
        """Serializes parameter tensors and working memory for atomic daily snapshots."""
        return {
            "capacity": self.capacity,
            "slab_size": self.slab_size,
            "W_ih": self.W_ih.data.cpu(),
            "b_ih": self.b_ih.data.cpu(),
            "W_hh": self.W_hh.data.cpu(),
            "b_hh": self.b_hh.data.cpu(),
            "W_out": self.W_out.data.cpu(),
            "b_out": self.b_out.data.cpu(),
            "H": self.H.cpu(),
            "free_slots": list(self.free_slots),
            "active_slots": list(self.active_slots),
        }

    def load_state_dict_custom(self, state_dict: dict[str, Any]) -> None:
        """Restores model state from checkpoint."""
        self.capacity = state_dict["capacity"]
        self.slab_size = state_dict["slab_size"]

        self.W_ih = nn.Parameter(state_dict["W_ih"].to(self.device))
        self.b_ih = nn.Parameter(state_dict["b_ih"].to(self.device))
        self.W_hh = nn.Parameter(state_dict["W_hh"].to(self.device))
        self.b_hh = nn.Parameter(state_dict["b_hh"].to(self.device))
        self.W_out = nn.Parameter(state_dict["W_out"].to(self.device))
        self.b_out = nn.Parameter(state_dict["b_out"].to(self.device))
        self.H = state_dict["H"].to(self.device)
        self.free_slots = list(state_dict["free_slots"])
        self.active_slots = set(state_dict["active_slots"])

    def memory_bytes(self) -> int:
        """Calculates total bytes consumed by all parameter tensors and hidden states."""
        total = 0
        for p in (self.W_ih, self.b_ih, self.W_hh, self.b_hh, self.W_out, self.b_out, self.H):
            total += p.numel() * p.element_size()
        return total
