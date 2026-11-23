"""
sim_core/tools/soak_test.py
Headless 1,500-agent 5-race soak test & atomic corruption rewind verifier.
Validates:
1. Multi-Tier Cognitive LOD execution across 1,500 agents.
2. Strict double-entry credit conservation (World Bank reserve + agent balances).
3. Zero mid-day disk writes.
4. Pure end-of-day World Goddess atomic 2PC save.
5. SHA-256 corruption rewind to the prior verified snapshot.
Usage:
  uv run python -m sim_core.tools.soak_test --ticks 600 --agents 1500 --verify-atomic-rewind
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import time
from pathlib import Path

from sim_core.bridge.mock_adapter import MockWorldAdapter
from sim_core.config import TICKS_PER_GAME_DAY
from sim_core.engine import SimulationEngine
from sim_core.races import BeasthumanSubLineage
from sim_core.schemas import Gender, RaceId


def run_soak_test(
    ticks: int = 600,
    num_agents: int = 1500,
    verify_atomic_rewind: bool = True,
    temp_dir: Path | None = None,
) -> bool:
    """
    Executes the 1,500-agent headless soak test:
    - Sets up temporary SQLite database, checkpoints, and god_ledger.
    - Spawns num_agents evenly across HUMAN, ELF, DRAGON, BEASTHUMAN, DEMON.
    - Runs ticks ticks.
    - Verifies credit conservation, zero mid-day disk writes, atomic 2PC, and rewind.
    """
    cleanup_temp = False
    if temp_dir is None:
        temp_dir = Path(tempfile.mkdtemp(prefix="gaia_soak_"))
        cleanup_temp = True

    db_path = temp_dir / "civilization.db"
    checkpoints_dir = temp_dir / "checkpoints"
    god_ledger_dir = temp_dir / "god_ledger"

    print("=" * 70)
    print("GAIA CIVILIZATION ENGINE: 1,500-AGENT HEADLESS SOAK TEST")
    print(f"Ticks: {ticks} | Agents: {num_agents} | Rewind Check: {verify_atomic_rewind}")
    print(f"Working Directory: {temp_dir}")
    print("=" * 70)

    try:
        adapter = MockWorldAdapter()
        engine = SimulationEngine(
            db_path=db_path,
            checkpoints_dir=checkpoints_dir,
            god_ledger_dir=god_ledger_dir,
            adapter=adapter,
            headless=True,
            initial_capacity=max(2048, num_agents + 512),
        )

        # ---------------------------------------------------------------------
        # 1. Spawn Agents Evenly Across 5 Races & 2 Genders
        # ---------------------------------------------------------------------
        print(f"[*] Spawning {num_agents} agents across 5 races...")
        races: list[RaceId] = ["HUMAN", "ELF", "DRAGON", "BEASTHUMAN", "DEMON"]
        genders: list[Gender] = ["BOY", "GIRL"]
        beasthuman_sublineages: list[BeasthumanSubLineage] = [
            "CAT_KIN",
            "WOLF_KIN",
            "DWARF",
            "BARBARIAN",
        ]

        for i in range(num_agents):
            race = races[i % 5]
            gender = genders[i % 2]
            sub_lineage = beasthuman_sublineages[i % 4] if race == "BEASTHUMAN" else None

            # Space agents across parcels
            gx = ((i % 50) - 25) * 32.0
            gz = ((i // 50) - 15) * 32.0
            from sim_core.schemas import Vec3

            pos_vec = Vec3(x=gx, y=0.0, z=gz)

            engine.spawn_agent(
                race=race,
                gender=gender,
                sub_lineage=sub_lineage,
                stage="ADULT",
                pos=pos_vec,
                initial_credits=20.0,
            )

        initial_credits = engine.bank.reserve_credits + sum(
            a.credits for a in engine.agents.values()
        )
        print(f"[+] Total initial credits: {initial_credits:.2f}")

        # ---------------------------------------------------------------------
        # 2. Verify Zero Mid-Day Disk Writes
        # ---------------------------------------------------------------------
        checkpoint_files_before = list(checkpoints_dir.glob("*"))
        ledger_files_before = list(god_ledger_dir.glob("*"))
        assert len(checkpoint_files_before) == 0, "Checkpoints directory not empty before run"
        assert len(ledger_files_before) == 0, "God ledger directory not empty before run"

        # ---------------------------------------------------------------------
        # 3. Execute Simulation Ticks
        # ---------------------------------------------------------------------
        print(f"[*] Stepping {ticks} simulation ticks...")
        t_start = time.perf_counter()

        for t in range(1, ticks + 1):
            engine.step_tick()

            # Random economic transfer every 10 ticks to test double-entry accounting
            if t % 10 == 0:
                agent_ids = list(engine.agents.keys())
                if len(agent_ids) >= 2:
                    sender = engine.agents[agent_ids[t % len(agent_ids)]]
                    recipient = engine.agents[agent_ids[(t + 1) % len(agent_ids)]]
                    engine.bank.transfer_credits(
                        sender=sender,
                        receiver=recipient,
                        amount=1.5,
                        memo="Trade exchange",
                    )

            # Check mid-day disk protection (before day boundary)
            if t % TICKS_PER_GAME_DAY != 0:
                assert len(list(checkpoints_dir.glob("*.pt"))) == 0, (
                    f"Mid-day disk write detected at tick {t}!"
                )

        elapsed = time.perf_counter() - t_start
        rate_hz = ticks / max(0.001, elapsed)
        ms_per_tick = (elapsed / ticks) * 1000.0
        print(
            f"[+] Completed {ticks} ticks in {elapsed:.2f}s "
            f"({rate_hz:.1f} Hz, {ms_per_tick:.2f} ms/tick)"
        )

        # ---------------------------------------------------------------------
        # 4. Credit Conservation Verification
        # ---------------------------------------------------------------------
        final_credits = engine.bank.reserve_credits + sum(a.credits for a in engine.agents.values())
        drift = abs(final_credits - initial_credits)
        print(
            f"[*] Verifying credit conservation: Initial={initial_credits:.2f}, "
            f"Final={final_credits:.2f}, Drift={drift:.6f}"
        )
        assert drift < 1e-4, f"Double-entry violation: credits drifted by {drift}!"
        print("[+] Strict double-entry credit conservation PASSED.")

        # ---------------------------------------------------------------------
        # 5. Atomic End-of-Day Two-Phase Commit Verification
        # ---------------------------------------------------------------------
        print("[*] Committing atomic daily checkpoint via World Goddess...")
        manifest1 = engine.commit_end_of_day()
        assert Path(manifest1.pt_path).exists(), "Checkpoint .pt file missing!"
        assert Path(manifest1.db_path).exists(), "Checkpoint .db file missing!"
        assert Path(manifest1.ledger_path).exists(), "God ledger .md file missing!"
        assert checkpoints_dir.joinpath("manifest.json").exists(), "manifest.json missing!"
        print("[+] Atomic end-of-day save PASSED.")

        # ---------------------------------------------------------------------
        # 6. Second Daily Checkpoint for Rewind Baseline
        # ---------------------------------------------------------------------
        print("[*] Creating second daily checkpoint (Day 2) for rewind verification...")
        for _ in range(10):
            engine.step_tick()
        manifest2 = engine.commit_end_of_day()
        assert Path(manifest2.pt_path).exists()
        assert Path(manifest2.db_path).exists()

        # ---------------------------------------------------------------------
        # 7. Corruption Rewind Verification
        # ---------------------------------------------------------------------
        if verify_atomic_rewind:
            print("[*] Deliberately corrupting latest Day 2 checkpoint to test automatic rewind...")
            # Corrupt the latest .pt file by truncating it
            with open(manifest2.pt_path, "wb") as f:
                f.write(b"CORRUPTED_BYTES_FOR_REWIND_TEST")

            print("[*] Running boot restore/rewind on corrupted checkpoint...")
            rewound_day, restored_manifest, status = (
                engine.checkpoint_mgr.restore_or_rewind_on_boot(live_db_path=db_path)
            )

            assert "CORRUPTION_REWIND" in status, f"Expected CORRUPTION_REWIND alert, got {status}"
            assert rewound_day == 1, f"Expected rewind to Day 1, got {rewound_day}"
            assert restored_manifest.day == 1
            print("[+] Automatic SHA-256 corruption rewind PASSED.")

        print("=" * 70)
        print("ALL SOAK TEST VERIFICATION GATES PASSED CLEANLY!")
        print("=" * 70)
        return True

    finally:
        if cleanup_temp and temp_dir.exists():
            shutil.rmtree(temp_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Gaia 1,500-Agent 4-Race Soak Test")
    parser.add_argument("--ticks", type=int, default=600, help="Number of ticks to simulate")
    parser.add_argument("--agents", type=int, default=1500, help="Number of agents to spawn")
    parser.add_argument(
        "--verify-atomic-rewind",
        action="store_true",
        default=True,
        help="Verify atomic SHA-256 corruption rewind",
    )
    args = parser.parse_args()

    success = run_soak_test(
        ticks=args.ticks,
        num_agents=args.agents,
        verify_atomic_rewind=args.verify_atomic_rewind,
    )
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
