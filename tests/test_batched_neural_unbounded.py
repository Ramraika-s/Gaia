"""
tests/test_batched_neural_unbounded.py
Phase 2 Mandatory Acceptance Tests:
- Unbounded slab growth: Spawning 2,500 agents expands capacity 2,048 -> 4,096.
- Hard stage masking: INFANT agents assign exact 0.0 probability to locked ADULT actions.
- GRU memory persistence across threat sequences and zero on birth.
- 200 batched training steps reduce outcome-prediction MSE with zero NaNs.
- NaN self-healing: ErrorHealer restores corrupted slot without corrupting neighbor slots.
- Survival gate and 4-channel social learning.
"""

import torch

from sim_core.neural.batched_self_net import BatchedAgentSelfNet
from sim_core.neural.shared_net import SharedSkillNet
from sim_core.neural.social_learning import SocialLearningSystem
from sim_core.neural.trainer import BatchedNeuralTrainer, RolloutBuffer
from sim_core.resilience.healer import ErrorHealer


def test_unbounded_slab_growth_expansion():
    """
    Acceptance Requirement:
    Spawning 2,500 agents cleanly expands capacity from 2,048 to 4,096
    without losing existing weights or GRU hidden states.
    """
    net = BatchedAgentSelfNet(initial_capacity=2048)
    assert net.capacity == 2048
    assert len(net.free_slots) == 2048

    # Spawn 100 initial agents and record initial parameters & hidden states
    initial_slots = [net.allocate_slot() for _ in range(100)]
    net.H[initial_slots[0]] = torch.randn(32)
    saved_h0 = net.H[initial_slots[0]].clone()
    saved_w0 = net.W_ih[initial_slots[0]].clone()

    # Allocate up to 2,500 agents total
    remaining_slots = [net.allocate_slot() for _ in range(2400)]
    all_slots = initial_slots + remaining_slots
    assert len(all_slots) == 2500

    # Capacity must dynamically expand by 1 slab (2048 -> 4096)
    assert net.capacity == 4096, f"Expected capacity 4096, got {net.capacity}"
    assert len(net.active_slots) == 2500
    assert len(net.free_slots) == 4096 - 2500

    # Ensure pre-expansion weights and hidden states were preserved bit-for-bit
    assert torch.equal(net.H[initial_slots[0]], saved_h0), "H[slot0] must survive slab growth"
    assert torch.equal(net.W_ih[initial_slots[0]], saved_w0), "W_ih[slot0] must survive growth"


def test_hard_stage_masking_infant_locked_actions():
    """
    Acceptance Requirement:
    INFANT agents assign exact 0.0 probability to locked ADULT actions:
    - GIVE_FAMILY_ALLOWANCE (idx 11)
    - MARKET_WTC_ORDER (idx 17)
    - PROPERTY_BUY_OR_SELL (idx 18)
    - DEFEND_OR_ATTACK (idx 15)
    """
    shared = SharedSkillNet()
    batch_size = 32
    x_shared = torch.randn(batch_size, 32)
    l_shared, _ = shared(x_shared)

    # Blending with neutral delta_l
    delta_l = torch.zeros(batch_size, 20)
    g_survival = torch.ones(batch_size, 1)
    l_raw = shared.blend_logits(l_shared, delta_l, g_survival)

    # 1. INFANT stage (stage 0): only 0..5 unlocked, 6..19 locked
    infant_stages = torch.zeros(batch_size, dtype=torch.long)
    masked_logits = shared.apply_stage_mask(l_raw, infant_stages)

    dist = shared.compute_action_distribution(masked_logits)
    probs = dist.probs  # (32, 20)

    # Verify locked actions have EXACT 0.0 probability
    locked_indices = [11, 15, 17, 18]  # allowance, attack, wtc, property
    for idx in locked_indices:
        assert torch.all(probs[:, idx] == 0.0), f"Action {idx} must have 0.0 probability for INFANT"

    # All actions 6..19 must be exact 0.0
    assert torch.all(probs[:, 6:] == 0.0), "All actions 6..19 must be 0.0 for INFANT"
    # Unlocked actions 0..5 must sum to 1.0
    assert torch.allclose(probs[:, 0:6].sum(dim=-1), torch.ones(batch_size), atol=1e-5)

    # 2. ADULT stage (stage 2): all 0..19 unlocked
    adult_stages = torch.full((batch_size,), 2, dtype=torch.long)
    adult_masked = shared.apply_stage_mask(l_raw, adult_stages)
    adult_dist = shared.compute_action_distribution(adult_masked)
    adult_probs = adult_dist.probs
    # All 20 actions have non-zero probability
    assert (adult_probs > 0.0).all(), "All actions must be available for ADULT"


def test_gru_working_memory_sequence_and_birth_reset():
    """
    Acceptance Requirement:
    Persistent H[slot] shifts outputs across threat sequences,
    and resets strictly to zero on new BIRTH.
    """
    net = BatchedAgentSelfNet(initial_capacity=100)
    slot = net.allocate_slot()
    slot_t = torch.tensor([slot], dtype=torch.long)

    # Initial H must be strictly zero on birth
    assert torch.all(net.H[slot] == 0.0), "H must be strictly zero on birth"

    # Sequence of threat steps: x_self danger / surprise spike
    # First step
    x_step1 = torch.zeros(1, 20)
    x_step1[0, 6] = 1.0  # high predicted reward
    out1, h1 = net(x_step1, slot_indices=slot_t)

    assert not torch.allclose(h1, torch.zeros_like(h1)), "H must evolve on input"
    assert torch.equal(net.H[slot], h1[0]), "Persistent H[slot] must match returned h1"

    # Second step with different threat input
    x_step2 = torch.zeros(1, 20)
    x_step2[0, 7] = -2.0  # high prediction error / surprise
    out2, h2 = net(x_step2, slot_indices=slot_t)

    # Outputs must shift across sequence due to persistent GRU hidden state
    assert not torch.allclose(out1, out2), "Outputs must shift across sequence"
    assert not torch.allclose(h1, h2), "Hidden states must evolve across sequence"

    # Now simulate breeding / newborn child: H must be strictly 0 on birth
    parent2 = net.allocate_slot()
    child_slot = net.allocate_slot(parent1_slot=slot, parent2_slot=parent2)
    assert torch.all(net.H[child_slot] == 0.0), "Newborn child hidden state H must be strictly zero"


def test_training_reduces_prediction_mse_no_nans():
    """
    Acceptance Requirement:
    200 batched training steps reduce outcome-prediction MSE with zero NaNs.
    """
    shared = SharedSkillNet()
    self_net = BatchedAgentSelfNet(initial_capacity=100)
    trainer = BatchedNeuralTrainer(shared, self_net)

    num_agents = 8
    slots = torch.tensor([self_net.allocate_slot() for _ in range(num_agents)], dtype=torch.long)

    # Synthetic target pattern for outcome predictor and consistent agent state features
    target_pattern = torch.tensor([0.2, 0.4, 0.6, 0.8, -0.2, -0.4, -0.6, -0.8])
    agent_features = torch.randn(num_agents, 20)

    initial_mse: float | None = None
    final_mse: float | None = None

    buffer = RolloutBuffer(capacity=100, steps=8)

    for epoch in range(200):
        # Generate 8 rollout steps
        for _ in range(8):
            obs_sh = torch.randn(num_agents, 32)
            obs_se = agent_features.clone()
            act = torch.zeros(num_agents, dtype=torch.long)
            lp = torch.full((num_agents,), -0.5)
            val = torch.zeros(num_agents, 1)
            # Extrinsic reward target
            r_ext = target_pattern.unsqueeze(-1)
            r_pred = torch.zeros(num_agents, 1)
            conf = torch.full((num_agents, 1), 0.5)
            stg = torch.zeros(num_agents, dtype=torch.long)  # INFANT stage (high plasticity)
            dne = torch.zeros(num_agents, dtype=torch.bool)

            buffer.insert(slots, obs_sh, obs_se, act, lp, val, r_ext, r_pred, conf, stg, dne)

        metrics = trainer.train_step(
            buffer, slots, neuroplasticity_mults=torch.full((num_agents,), 2.0)
        )

        assert not torch.isnan(torch.tensor(metrics["loss_pred"])), (
            f"NaN in loss_pred at step {epoch}"
        )
        assert not torch.isnan(torch.tensor(metrics["loss_total"])), (
            f"NaN in loss_total at step {epoch}"
        )

        if epoch == 0:
            initial_mse = metrics["loss_pred"]
        if epoch == 199:
            final_mse = metrics["loss_pred"]

    assert initial_mse is not None and final_mse is not None
    # Training must reduce prediction error over 200 epochs
    assert final_mse < initial_mse, (
        f"Prediction MSE did not decrease: initial={initial_mse:.4f}, final={final_mse:.4f}"
    )


def test_nan_self_healing_without_corrupting_neighbors():
    """
    Acceptance Requirement:
    Injecting NaN into one agent's GRU hidden state is caught and restored
    via ErrorHealer without corrupting any other slot.
    """
    healer = ErrorHealer()
    net = BatchedAgentSelfNet(initial_capacity=100, healer=healer)

    slot_a = net.allocate_slot()
    slot_b = net.allocate_slot()
    slot_c = net.allocate_slot()

    # Set known healthy states
    net.H[slot_a] = torch.full((32,), 1.0)
    net.H[slot_b] = torch.full((32,), 2.0)
    net.H[slot_c] = torch.full((32,), 3.0)

    # Corrupt ONLY slot_b with NaNs
    net.H[slot_b] = float("nan")

    batch_slots = torch.tensor([slot_a, slot_b, slot_c], dtype=torch.long)
    x_self = torch.randn(3, 20)

    out, h_next = net(x_self, slot_indices=batch_slots, day=1, tick=42)

    # 1. ErrorHealer must have logged the incident
    assert healer.get_fault_count(1, "TENSOR_NAN_INF") == 1

    # 2. Corrupted slot_b must be restored to finite clean state
    assert torch.isfinite(out).all(), "All batch outputs must be finite"
    assert torch.isfinite(h_next).all(), "All hidden states must be finite"
    assert torch.isfinite(net.H[slot_b]).all(), "H[slot_b] must be restored to finite"

    # 3. Healthy neighbors slot_a and slot_c must remain completely uncorrupted
    assert torch.isfinite(net.H[slot_a]).all()
    assert torch.isfinite(net.H[slot_c]).all()
    assert not torch.allclose(net.H[slot_a], torch.zeros(32)), "slot_a must preserve its state"
    assert not torch.allclose(net.H[slot_c], torch.zeros(32)), "slot_c must preserve its state"


def test_survival_gate_clamps_preference_modulation():
    """
    Acceptance Requirement:
    g_survival clamps to 0.25 when health / max_health < 0.25 or hunger < 15.0.
    """
    health = torch.tensor([1.0, 0.24, 0.8, 0.10])
    hunger = torch.tensor([80.0, 80.0, 14.0, 5.0])

    g = SharedSkillNet.compute_survival_gate(health, hunger)
    assert g[0].item() == 1.0, "Healthy agent must have g_survival = 1.0"
    assert g[1].item() == 0.25, "Critical health must clamp g_survival to 0.25"
    assert g[2].item() == 0.25, "Critical hunger must clamp g_survival to 0.25"
    assert g[3].item() == 0.25, "Both critical must clamp g_survival to 0.25"


def test_social_learning_four_channels():
    """
    Acceptance Requirement:
    Validates all 4 social learning channels:
    1. Parental Care & Teaching (+0.04 * (1 + teach_skill))
    2. Peer Observation (+0.015 * trust * plasticity)
    3. World Library Consultation (+0.08 boost up to 0.60)
    4. Cultural Tradition Adoption
    """
    child_skills = {"walk": 0.1, "forage": 0.2}

    # Channel 1: Parental Teaching
    d1 = SocialLearningSystem.apply_parental_teaching(
        child_skills, "forage", parent_teach_skill=0.5, dist_meters=4.0
    )
    assert round(d1, 4) == round(0.04 * 1.5, 4)  # +0.06
    assert round(child_skills["forage"], 4) == 0.26

    # Channel 2: Peer Observation
    peer_skills = {"forage": 0.5}
    d2 = SocialLearningSystem.apply_peer_observation(
        child_skills, peer_skills, "forage", trust=0.8, observer_stage="CHILD", peer_success=True
    )
    # delta = 0.015 * 0.8 * 1.0 = 0.012
    assert round(d2, 4) == 0.012

    # Channel 3: World Library Consultation
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

    # Reading same book again yields 0 boost
    d3_repeat = SocialLearningSystem.apply_library_reading(
        child_skills,
        "forage",
        is_elder_approved=True,
        already_read_book_ids=read_books,
        book_id="book_forage_1",
    )
    assert d3_repeat == 0.0

    # Channel 4: Cultural Tradition Adoption
    personal_traditions: set[str] = set()
    adopted = SocialLearningSystem.transmit_cultural_tradition(
        "CHILD", personal_traditions, "dragon_solstice_vigil", event_active=True
    )
    assert adopted is True
    assert "dragon_solstice_vigil" in personal_traditions
