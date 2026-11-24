"""
sim_core/tools/bench_tensors.py
Benchmark profiling 10,000-agent slab-grown forward-pass latency,
2,048-slot dynamic slab allocation, and neural tensor RAM usage.
Supports 3-Tier HierarchicalBrain by default and legacy 2-tier with --legacy-2tier.
Follows NEURAL_AND_LIFECYCLE_SPEC.md, HYBRID_COGNITIVE_AND_LLM_SPEC.md, and AGENTS.md.
"""

from __future__ import annotations

import argparse
import sys
import time

import torch

from sim_core.brains.hierarchical_brain import HierarchicalBrain
from sim_core.brains.profession_nets import PROFESSIONS
from sim_core.neural.batched_self_net import BatchedAgentSelfNet
from sim_core.neural.shared_net import SharedSkillNet


def run_benchmark_legacy_2tier(
    num_agents: int = 10000,
    num_steps: int = 50,
) -> dict[str, float]:
    """
    Executes the legacy 2-tier benchmark (SharedSkillNet + BatchedAgentSelfNet)
    over num_agents for num_steps.
    """
    print(f"\n{'=' * 70}")
    print(f"GAIA NEURAL BENCHMARK (LEGACY 2-TIER): {num_agents:,} AGENTS | {num_steps} STEPS")
    print(f"{'=' * 70}")

    device = torch.device("cpu")
    shared_net = SharedSkillNet().to(device)
    self_net = BatchedAgentSelfNet(initial_capacity=2048, device=device)

    # 1. Slab Allocation Phase
    t_alloc_start = time.perf_counter()
    allocated_slots = [self_net.allocate_slot() for _ in range(num_agents)]
    t_alloc = (time.perf_counter() - t_alloc_start) * 1000.0

    capacity = self_net.capacity
    print(
        f"[SLAB_ALLOCATION] Allocated {num_agents:,} agents into capacity {capacity:,} "
        f"in {t_alloc:.2f} ms."
    )

    # 2. RAM Profiling
    self_net_bytes = self_net.memory_bytes()
    shared_net_bytes = sum(p.numel() * p.element_size() for p in shared_net.parameters())
    total_bytes = self_net_bytes + shared_net_bytes
    total_mb = total_bytes / (1024.0 * 1024.0)

    print(
        f"[RAM_USAGE] BatchedAgentSelfNet: {self_net_bytes / (1024 * 1024):.2f} MB | "
        f"SharedSkillNet: {shared_net_bytes / 1024:.2f} KB | Total: {total_mb:.2f} MB"
    )

    # 3. Warm-up step
    slot_tensor = torch.tensor(allocated_slots, dtype=torch.long, device=device)
    x_shared = torch.randn(num_agents, 32, device=device)
    x_self = torch.randn(num_agents, 20, device=device)
    stage_indices = torch.randint(0, 4, (num_agents,), device=device)
    health_ratio = torch.ones(num_agents, 1, device=device)
    hunger = torch.full((num_agents, 1), 80.0, device=device)

    with torch.no_grad():
        for _ in range(3):
            l_shared, _ = shared_net(x_shared)
            out_self, _ = self_net(x_self, slot_indices=slot_tensor)
            g_survival = SharedSkillNet.compute_survival_gate(health_ratio, hunger)
            l_raw = shared_net.blend_logits(l_shared, out_self[:, 0:20], g_survival)
            _ = shared_net.apply_stage_mask(l_raw, stage_indices)

    # 4. Timed Steps
    step_times_ms: list[float] = []
    print(f"[FORWARD_PASS] Executing {num_steps} batched forward passes...")

    with torch.no_grad():
        for _step in range(num_steps):
            x_shared.normal_()
            x_self.normal_()

            t0 = time.perf_counter()

            l_shared, _ = shared_net(x_shared)
            out_self, _ = self_net(x_self, slot_indices=slot_tensor)
            g_survival = SharedSkillNet.compute_survival_gate(health_ratio, hunger)
            l_raw = shared_net.blend_logits(l_shared, out_self[:, 0:20], g_survival)
            masked_logits = shared_net.apply_stage_mask(l_raw, stage_indices)
            conf = torch.sigmoid(out_self[:, 21:22])
            _ = shared_net.compute_action_distribution(masked_logits, conf)

            t1 = time.perf_counter()
            step_times_ms.append((t1 - t0) * 1000.0)

    avg_ms = sum(step_times_ms) / len(step_times_ms)
    min_ms = min(step_times_ms)
    max_ms = max(step_times_ms)
    sorted_times = sorted(step_times_ms)
    p95_ms = sorted_times[int(0.95 * len(sorted_times))]

    print(
        f"[PERFORMANCE] Avg: {avg_ms:.2f} ms/step | Min: {min_ms:.2f} ms | "
        f"Max: {max_ms:.2f} ms | P95: {p95_ms:.2f} ms"
    )
    print(f"{'=' * 70}\n")

    return {
        "num_agents": float(num_agents),
        "capacity": float(capacity),
        "ram_mb": total_mb,
        "avg_ms": avg_ms,
        "min_ms": min_ms,
        "max_ms": max_ms,
        "p95_ms": p95_ms,
    }


def run_benchmark_3tier(
    num_agents: int = 10000,
    num_steps: int = 50,
) -> dict[str, float]:
    """
    Executes the canonical 3-tier HierarchicalBrain benchmark:
    - Tier 1: SharedLivingNet (survival & reflex)
    - Tier 2: Grouped Profession Nets (10 professions Lv. 1-10)
    - Tier 3: BatchedAgentSelfNet (2,048-slab GRU individuality)
    - Personality/Mood action logit bias
    - Life-stage masking
    """
    print(f"\n{'=' * 70}")
    print(f"GAIA NEURAL BENCHMARK (3-TIER HIERARCHICAL): {num_agents:,} AGENTS | {num_steps} STEPS")
    print(f"{'=' * 70}")

    device = torch.device("cpu")
    brain = HierarchicalBrain(initial_capacity=2048, device=device)

    # 1. Slab Allocation Phase
    t_alloc_start = time.perf_counter()
    allocated_slots = [brain.tier3_self.allocate_slot() for _ in range(num_agents)]
    t_alloc = (time.perf_counter() - t_alloc_start) * 1000.0

    capacity = brain.tier3_self.capacity
    print(
        f"[SLAB_ALLOCATION] Allocated {num_agents:,} agents into capacity {capacity:,} "
        f"in {t_alloc:.2f} ms."
    )

    # 2. RAM Profiling
    tier3_bytes = brain.tier3_self.memory_bytes()
    tier1_bytes = sum(p.numel() * p.element_size() for p in brain.tier1_living.parameters())
    tier2_bytes = sum(
        sum(p.numel() * p.element_size() for p in net.parameters())
        for net in brain.tier2_profession.nets.values()
    )
    buffer_bytes = sum(b.numel() * b.element_size() for b in brain.buffers())
    total_bytes = tier3_bytes + tier1_bytes + tier2_bytes + buffer_bytes
    total_mb = total_bytes / (1024.0 * 1024.0)

    print(
        f"[RAM_USAGE] Tier 3 (SelfNet Slab): {tier3_bytes / (1024 * 1024):.2f} MB | "
        f"Tier 1 (LivingNet): {tier1_bytes / 1024:.2f} KB | "
        f"Tier 2 (ProfessionNets): {tier2_bytes / 1024:.2f} KB | "
        f"Buffers: {buffer_bytes / 1024:.2f} KB | Total: {total_mb:.2f} MB"
    )

    # 3. Input Setup: Representative distribution across professions and life stages
    x_living = torch.randn(num_agents, 24, device=device)
    chunk = max(1, num_agents // len(PROFESSIONS))
    professions: list[str] = []
    for p in PROFESSIONS:
        professions.extend([p] * chunk)
    if len(professions) < num_agents:
        professions.extend(["CITIZEN"] * (num_agents - len(professions)))
    elif len(professions) > num_agents:
        professions = professions[:num_agents]

    levels = torch.randint(1, 11, (num_agents,), device=device)
    stages: list[str] = ["ADULT"] * num_agents
    active_effects: list[dict[str, float]] = [{}] * num_agents
    personalities = torch.randn(num_agents, 15, device=device)
    health_ratios = torch.ones(num_agents, device=device)
    hungers = torch.full((num_agents,), 80.0, device=device)

    # Warm-up steps
    with torch.no_grad():
        for _ in range(3):
            brain.forward_batch(
                slot_indices=allocated_slots,
                x_living=x_living,
                professions=professions,
                levels=levels,
                active_effects=active_effects,
                stages=stages,
                personalities=personalities,
                health_ratios=health_ratios,
                hungers=hungers,
            )

    # 4. Timed Steps
    step_times_ms: list[float] = []
    print(f"[FORWARD_PASS] Executing {num_steps} batched forward passes...")

    with torch.no_grad():
        for _step in range(num_steps):
            x_living.normal_()

            t0 = time.perf_counter()

            masked_logits, values = brain.forward_batch(
                slot_indices=allocated_slots,
                x_living=x_living,
                professions=professions,
                levels=levels,
                active_effects=active_effects,
                stages=stages,
                personalities=personalities,
                health_ratios=health_ratios,
                hungers=hungers,
            )

            t1 = time.perf_counter()
            step_times_ms.append((t1 - t0) * 1000.0)

    avg_ms = sum(step_times_ms) / len(step_times_ms)
    min_ms = min(step_times_ms)
    max_ms = max(step_times_ms)
    sorted_times = sorted(step_times_ms)
    p95_ms = sorted_times[int(0.95 * len(sorted_times))]

    print(
        f"[PERFORMANCE] Avg: {avg_ms:.2f} ms/step | Min: {min_ms:.2f} ms | "
        f"Max: {max_ms:.2f} ms | P95: {p95_ms:.2f} ms"
    )
    print(f"{'=' * 70}\n")

    return {
        "num_agents": float(num_agents),
        "capacity": float(capacity),
        "ram_mb": total_mb,
        "avg_ms": avg_ms,
        "min_ms": min_ms,
        "max_ms": max_ms,
        "p95_ms": p95_ms,
    }


def run_benchmark(
    num_agents: int = 10000,
    num_steps: int = 50,
    legacy_2tier: bool = False,
) -> dict[str, float]:
    """Top-level benchmark runner defaulting to 3-tier HierarchicalBrain."""
    if legacy_2tier:
        return run_benchmark_legacy_2tier(num_agents=num_agents, num_steps=num_steps)
    return run_benchmark_3tier(num_agents=num_agents, num_steps=num_steps)


def main() -> None:
    parser = argparse.ArgumentParser(description="Gaia Neural Tensor Benchmark")
    parser.add_argument("--agents", type=int, default=10000, help="Number of living neural agents")
    parser.add_argument("--steps", type=int, default=50, help="Number of forward-pass steps")
    parser.add_argument(
        "--legacy-2tier",
        action="store_true",
        help="Run legacy 2-tier benchmark (SharedSkillNet + BatchedAgentSelfNet)",
    )
    args = parser.parse_args()

    metrics = run_benchmark(
        num_agents=args.agents,
        num_steps=args.steps,
        legacy_2tier=args.legacy_2tier,
    )

    # Acceptance Assertions:
    if metrics["avg_ms"] > 25.0:
        print(
            f"FAILED: Average latency {metrics['avg_ms']:.2f} ms exceeds 25.0 ms threshold!",
            file=sys.stderr,
        )
        sys.exit(1)

    if metrics["ram_mb"] > 250.0:
        print(
            f"FAILED: Neural RAM {metrics['ram_mb']:.2f} MB exceeds 250.0 MB threshold!",
            file=sys.stderr,
        )
        sys.exit(1)

    print("ALL BENCHMARK CRITERIA SATISFIED (Latency < 25ms, RAM < 250MB).")


if __name__ == "__main__":
    main()
