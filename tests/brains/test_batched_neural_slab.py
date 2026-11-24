"""
tests/brains/test_batched_neural_slab.py
BatchedAgentSelfNet unbounded 2,048-slab growth, hard developmental stage masking,
GRU working memory dynamics, NaN self-healing, survival gating, and social learning.
"""

from __future__ import annotations

import pytest
import torch

from sim_core.neural.batched_self_net import BatchedAgentSelfNet
from sim_core.neural.shared_net import SharedSkillNet
from sim_core.neural.social_learning import SocialLearningSystem
from sim_core.neural.trainer import BatchedNeuralTrainer, RolloutBuffer
from sim_core.resilience.healer import ErrorHealer


@pytest.mark.slow
def test_unbounded_slab_growth_expansion() -> None:
    """
    Spawning 2,500 agents cleanly expands capacity 2,048 -> 4,096 without losing
    weights or GRU states.
    """
    net = BatchedAgentSelfNet(initial_capacity=2048)
    assert net.capacity == 2048
    assert len(net.free_slots) == 2048

    initial_slots = [net.allocate_slot() for _ in range(100)]
    net.H[initial_slots[0]] = torch.randn(32)
    saved_h0 = net.H[initial_slots[0]].clone()
    saved_w0 = net.W_ih[initial_slots[0]].clone()

    remaining_slots = [net.allocate_slot() for _ in range(2400)]
    all_slots = initial_slots + remaining_slots
    assert len(all_slots) == 2500

    assert net.capacity == 4096
    assert len(net.active_slots) == 2500
    assert len(net.free_slots) == 4096 - 2500

    assert torch.equal(net.H[initial_slots[0]], saved_h0)
    assert torch.equal(net.W_ih[initial_slots[0]], saved_w0)


def test_hard_stage_masking_infant_locked_actions() -> None:
    """INFANT agents assign exact 0.0 probability to locked adult actions."""
    shared = SharedSkillNet()
    batch_size = 32
    x_shared = torch.randn(batch_size, 32)
    l_shared, _ = shared(x_shared)

    delta_l = torch.zeros(batch_size, 20)
    g_survival = torch.ones(batch_size, 1)
    l_raw = shared.blend_logits(l_shared, delta_l, g_survival)

    infant_stages = torch.zeros(batch_size, dtype=torch.long)
    masked_logits = shared.apply_stage_mask(l_raw, infant_stages)

    dist = shared.compute_action_distribution(masked_logits)
    probs = dist.probs

    # Verify locked actions have EXACT 0.0 probability
    locked_indices = [11, 15, 17, 18]
    for idx in locked_indices:
        assert torch.all(probs[:, idx] == 0.0)

    assert torch.all(probs[:, 6:] == 0.0)
    assert torch.allclose(probs[:, 0:6].sum(dim=-1), torch.ones(batch_size), atol=1e-5)

    adult_stages = torch.full((batch_size,), 2, dtype=torch.long)
    adult_masked = shared.apply_stage_mask(l_raw, adult_stages)
    adult_dist = shared.compute_action_distribution(adult_masked)
    assert (adult_dist.probs > 0.0).all()


def test_gru_working_memory_sequence_and_birth_reset() -> None:
    """Persistent H[slot] shifts across threat inputs and resets strictly to zero on new birth."""
    net = BatchedAgentSelfNet(initial_capacity=100)
    slot = net.allocate_slot()
    slot_t = torch.tensor([slot], dtype=torch.long)

    assert torch.all(net.H[slot] == 0.0)

    x_step1 = torch.zeros(1, 20)
    x_step1[0, 6] = 1.0
    out1, h1 = net(x_step1, slot_indices=slot_t)
    assert not torch.allclose(h1, torch.zeros_like(h1))
    assert torch.equal(net.H[slot], h1[0])

    x_step2 = torch.zeros(1, 20)
    x_step2[0, 7] = -2.0
    out2, h2 = net(x_step2, slot_indices=slot_t)

    assert not torch.allclose(out1, out2)
    assert not torch.allclose(h1, h2)

    parent2 = net.allocate_slot()
    child_slot = net.allocate_slot(parent1_slot=slot, parent2_slot=parent2)
    assert torch.all(net.H[child_slot] == 0.0)


@pytest.mark.slow
def test_training_reduces_prediction_mse_no_nans() -> None:
    """200 batched training steps reduce outcome-prediction MSE with zero NaNs."""
    shared = SharedSkillNet()
    self_net = BatchedAgentSelfNet(initial_capacity=100)
    trainer = BatchedNeuralTrainer(shared, self_net)

    num_agents = 8
    slots = torch.tensor([self_net.allocate_slot() for _ in range(num_agents)], dtype=torch.long)

    target_pattern = torch.tensor([0.2, 0.4, 0.6, 0.8, -0.2, -0.4, -0.6, -0.8])
    agent_features = torch.randn(num_agents, 20)

    initial_mse: float | None = None
    final_mse: float | None = None

    buffer = RolloutBuffer(capacity=100, steps=8)

    for epoch in range(200):
        for _ in range(8):
            obs_sh = torch.randn(num_agents, 32)
            obs_se = agent_features.clone()
            act = torch.zeros(num_agents, dtype=torch.long)
            lp = torch.full((num_agents,), -0.5)
            val = torch.zeros(num_agents, 1)
            r_ext = target_pattern.unsqueeze(-1)
            r_pred = torch.zeros(num_agents, 1)
            conf = torch.full((num_agents, 1), 0.5)
            stg = torch.zeros(num_agents, dtype=torch.long)
            dne = torch.zeros(num_agents, dtype=torch.bool)

            buffer.insert(slots, obs_sh, obs_se, act, lp, val, r_ext, r_pred, conf, stg, dne)

        metrics = trainer.train_step(
            buffer, slots, neuroplasticity_mults=torch.full((num_agents,), 2.0)
        )
        assert not torch.isnan(torch.tensor(metrics["loss_pred"]))
        assert not torch.isnan(torch.tensor(metrics["loss_total"]))

        if epoch == 0:
            initial_mse = metrics["loss_pred"]
        if epoch == 199:
            final_mse = metrics["loss_pred"]

    assert initial_mse is not None and final_mse is not None
    assert final_mse < initial_mse


def test_nan_self_healing_without_corrupting_neighbors() -> None:
    """ErrorHealer catches and restores NaN in slot H without corrupting neighbor slots."""
    healer = ErrorHealer()
    net = BatchedAgentSelfNet(initial_capacity=100, healer=healer)

    slot_a = net.allocate_slot()
    slot_b = net.allocate_slot()
    slot_c = net.allocate_slot()

    net.H[slot_a] = torch.full((32,), 1.0)
    net.H[slot_b] = torch.full((32,), 2.0)
    net.H[slot_c] = torch.full((32,), 3.0)

    # Corrupt ONLY slot_b with NaNs
    net.H[slot_b] = float("nan")

    batch_slots = torch.tensor([slot_a, slot_b, slot_c], dtype=torch.long)
    x_self = torch.randn(3, 20)

    out, h_next = net(x_self, slot_indices=batch_slots, day=1, tick=42)

    assert healer.get_fault_count(1, "TENSOR_NAN_INF") == 1
    assert torch.isfinite(out).all()
    assert torch.isfinite(h_next).all()
    assert torch.isfinite(net.H[slot_b]).all()

    assert torch.isfinite(net.H[slot_a]).all()
    assert torch.isfinite(net.H[slot_c]).all()
    assert not torch.allclose(net.H[slot_a], torch.zeros(32))
    assert not torch.allclose(net.H[slot_c], torch.zeros(32))


def test_survival_gate_clamps_preference_modulation() -> None:
    """g_survival clamps to 0.25 when health / max_health < 0.25 or hunger < 15.0."""
    health = torch.tensor([1.0, 0.24, 0.8, 0.10])
    hunger = torch.tensor([80.0, 80.0, 14.0, 5.0])

    g = SharedSkillNet.compute_survival_gate(health, hunger)
    assert g[0].item() == 1.0
    assert g[1].item() == 0.25
    assert g[2].item() == 0.25
    assert g[3].item() == 0.25


def test_social_learning_four_channels() -> None:
    """
    Validates parental teaching, peer observation, library reading, and tradition
    transmission.
    """
    child_skills = {"walk": 0.1, "forage": 0.2}

    # 1. Parental teaching
    d1 = SocialLearningSystem.apply_parental_teaching(
        child_skills, "forage", parent_teach_skill=0.5, dist_meters=4.0
    )
    assert round(d1, 4) == round(0.04 * 1.5, 4)
    assert round(child_skills["forage"], 4) == 0.26

    # 2. Peer observation
    peer_skills = {"forage": 0.5}
    d2 = SocialLearningSystem.apply_peer_observation(
        child_skills, peer_skills, "forage", trust=0.8, observer_stage="CHILD", peer_success=True
    )
    assert round(d2, 4) == 0.012

    # 3. Library reading
    read_books: set[str] = set()
    d3 = SocialLearningSystem.apply_library_reading(
        child_skills,
        "forage",
        is_elder_approved=True,
        already_read_book_ids=read_books,
        book_id="book_forage_1",
    )
    assert round(d3, 4) == 0.08
    assert "book_forage_1" in read_books

    # Duplicate reading yields 0
    d3_repeat = SocialLearningSystem.apply_library_reading(
        child_skills,
        "forage",
        is_elder_approved=True,
        already_read_book_ids=read_books,
        book_id="book_forage_1",
    )
    assert d3_repeat == 0.0

    # 4. Tradition transmission
    traditions: set[str] = set()
    adopted = SocialLearningSystem.transmit_cultural_tradition(
        "CHILD", traditions, "dragon_solstice_vigil", event_active=True
    )
    assert adopted is True
    assert "dragon_solstice_vigil" in traditions


def test_batched_self_net_exact_contiguity_safety() -> None:
    """BatchedAgentSelfNet safely handles non-contiguous slot indices without state corruption."""
    net = BatchedAgentSelfNet(initial_capacity=64)
    slots = [net.allocate_slot() for _ in range(10)]
    assert slots == list(range(10))

    non_contig_tensor = torch.tensor([0, 1, 5, 2, 4], dtype=torch.long)
    inputs = torch.randn(5, 20)

    H_init = net.H.clone()
    outputs, values = net.forward(inputs, non_contig_tensor)
    assert outputs.shape == (5, 22)
    assert values.shape == (5, 32)
    assert not torch.isnan(outputs).any()

    # Compare with individual passes
    net.H.copy_(H_init)
    for i, slot_id in enumerate([0, 1, 5, 2, 4]):
        single_slot = torch.tensor([slot_id], dtype=torch.long)
        single_input = inputs[i : i + 1]
        single_out, single_val = net.forward(single_input, single_slot)
        assert torch.allclose(outputs[i : i + 1], single_out, atol=1e-5)
        assert torch.allclose(values[i : i + 1], single_val, atol=1e-5)
