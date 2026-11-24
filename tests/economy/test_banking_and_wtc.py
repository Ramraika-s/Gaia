# tests/economy/test_banking_and_wtc.py
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.launch_gaia import spawn_initial_population
from sim_core.bridge.mock_adapter import MockWorldAdapter
from sim_core.engine import SimulationEngine
from sim_core.god_console.cli import RichGodConsole
from sim_core.schemas import Gender, RaceId
from sim_core.society.wtc_market import WTCExchange


@pytest.mark.slow
def test_strict_credit_conservation_across_600_ticks(engine: SimulationEngine) -> None:
    """Verifies that total credits in the system remain strictly conserved across 600 ticks."""
    # Spawn 100 agents across 4 races
    races: list[RaceId] = ["HUMAN", "ELF", "DRAGON", "BEASTHUMAN"]
    genders: list[Gender] = ["BOY", "GIRL"]
    for i in range(100):
        engine.spawn_agent(
            race=races[i % 4],
            gender=genders[i % 2],
            initial_credits=25.0,
            stage="ADULT",
        )

    initial_total = engine.bank.reserve_credits + sum(a.credits for a in engine.agents.values())
    agent_ids = list(engine.agents.keys())

    # Step 600 ticks with economic operations (transfers and loan cycles)
    for t in range(1, 601):
        engine.step_tick()

        # Transfers between random agents
        if t % 5 == 0 and len(agent_ids) >= 2:
            sender = engine.agents[agent_ids[t % len(agent_ids)]]
            receiver = engine.agents[agent_ids[(t + 1) % len(agent_ids)]]
            engine.bank.transfer_credits(sender, receiver, amount=2.0)

        # Issue and repay loans
        if t == 50 and len(agent_ids) > 0:
            borrower = engine.agents[agent_ids[0]]
            engine.bank.issue_loan(borrower, principal=100.0, holder_type="AGENT", current_tick=t)

        if t == 100 and len(agent_ids) > 0:
            borrower = engine.agents[agent_ids[0]]
            loans = list(engine.bank.loans.keys())
            if loans:
                engine.bank.process_loan_repayment(borrower, loans[0], installment=50.0)

    final_total = engine.bank.reserve_credits + sum(a.credits for a in engine.agents.values())
    drift = abs(final_total - initial_total)
    assert drift < 1e-4, f"Drift {drift:.6f} exceeds tolerance!"


def test_credit_transfer_double_entry_protection(engine: SimulationEngine) -> None:
    """Verifies fail-closed transfer rejection if sender lacks balance or amount <= 0."""
    alice = engine.spawn_agent(race="HUMAN", gender="GIRL", stage="ADULT", initial_credits=50.0)
    bob = engine.spawn_agent(race="ELF", gender="BOY", stage="ADULT", initial_credits=10.0)

    # Valid transfer
    ok, _ = engine.bank.transfer_credits(alice, bob, amount=20.0)
    assert ok is True
    assert alice.credits == 30.0
    assert bob.credits == 30.0

    # Overdraft transfer rejected
    ok_overdraft, _ = engine.bank.transfer_credits(alice, bob, amount=50.0)
    assert ok_overdraft is False
    assert alice.credits == 30.0
    assert bob.credits == 30.0

    # Zero or negative transfer rejected
    ok_zero, _ = engine.bank.transfer_credits(alice, bob, amount=0.0)
    assert ok_zero is False
    ok_neg, _ = engine.bank.transfer_credits(alice, bob, amount=-10.0)
    assert ok_neg is False


def test_wtc_cpi_inflation_under_winter_scarcity_and_borrowing() -> None:
    """Verifies that high borrowing (M) coupled with Winter scarcity (low Q) raises WTC CPI."""
    wtc = WTCExchange(base_m=10000.0, base_q=10000.0)
    assert wtc.cpi == 1.0

    # Baseline market clearing with balanced money supply M=10,000, real output Q=10,000
    baseline_cpi = wtc.update_macro_aggregates(money_supply_m=10000.0, real_output_q=10000.0)
    assert 0.95 <= baseline_cpi <= 1.05

    # Simulate heavy borrowing (M increases to 25,000) and Winter scarcity (Q drops to 5,000)
    cpi = wtc.update_macro_aggregates(money_supply_m=25000.0, real_output_q=5000.0)

    # CPI must measurably increase under M/Q expansion
    assert cpi > baseline_cpi
    assert cpi >= 2.0, f"Expected CPI inflation >= 2.0 under 25k/5k, got {cpi}"

    # Verify price clamp: commodity prices cannot move more than +-15% in a single market clear
    wtc_clamp = WTCExchange()
    old_food_price = wtc_clamp.current_prices["food"]

    # Place high bid and ask that would raw-clear at 10x the price
    wtc_clamp.place_order("agent_1", "BUY", "food", quantity=10.0, limit_price=10.0)
    wtc_clamp.place_order("agent_2", "SELL", "food", quantity=10.0, limit_price=10.0)
    wtc_clamp.clear_market(current_day=1, current_tick=60)

    new_food_price = wtc_clamp.current_prices["food"]
    ratio = new_food_price / old_food_price
    assert ratio <= 1.151, f"Price clamp violated: ratio was {ratio}"


@pytest.mark.slow
def test_wtc_calibration_and_freeze(tmp_path: Path) -> None:
    """Verifies baseline CPI calibration at 1,500 agents and God Console market freeze."""
    engine = SimulationEngine(
        db_path=tmp_path / "civ_wtc.db",
        checkpoints_dir=tmp_path / "checkpoints",
        god_ledger_dir=tmp_path / "god_ledger",
        adapter=MockWorldAdapter(),
        headless=True,
    )

    spawn_initial_population(engine, num_agents=1500)
    assert len(engine.agents) >= 1500

    # CPI must start at exactly 1.000 after calibrate_baseline()
    assert abs(engine.wtc.cpi - 1.0) < 1e-4

    # Single-source-of-truth Q calculation preserves CPI=1.000 during civic loop step
    engine._step_civic_loop()
    assert abs(engine.wtc.cpi - 1.0) < 0.05

    cli = RichGodConsole(engine)
    assert engine.wtc.frozen is False

    # Freeze market via console
    out1 = cli._cmd_wtc_action(["freeze"])
    assert "frozen" in out1.lower()
    assert engine.wtc.frozen is True

    # Attempt order while frozen
    ok, reason = engine.wtc.place_order("agent_1", "BUY", "food", 10.0, 5.0)
    assert not ok
    assert reason == "MARKET_FROZEN"

    # Unfreeze market via console
    out2 = cli._cmd_wtc_action(["freeze"])
    assert "unfrozen" in out2.lower()
    assert engine.wtc.frozen is False
