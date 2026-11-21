"""
tests/test_economy_double_entry_inflation.py
Acceptance tests for Phase 3B:
1. Strict closed-loop double-entry credit conservation across 600 ticks.
2. WTC Fisher CPI inflation under Winter scarcity and heavy borrowing.
3. 16x16m property probate cascade, settlement escheatment, and wilderness UNCLAIMED status.
"""

from __future__ import annotations

from pathlib import Path

from sim_core.bridge.mock_adapter import MockWorldAdapter
from sim_core.engine import SimulationEngine
from sim_core.schemas import AgentRecord, ParcelRecord
from sim_core.society.property import PropertyManager
from sim_core.society.wtc_market import WTCExchange


def test_strict_credit_conservation_across_600_ticks(tmp_path: Path, test_db_path: Path):
    """Verifies that total credits in the system remain strictly conserved across 600 ticks."""
    checkpoints_dir = tmp_path / "checkpoints"
    god_ledger_dir = tmp_path / "god_ledger"

    engine = SimulationEngine(
        db_path=test_db_path,
        checkpoints_dir=checkpoints_dir,
        god_ledger_dir=god_ledger_dir,
        adapter=MockWorldAdapter(),
        headless=True,
        initial_capacity=2048,
    )

    # Spawn 100 agents across 4 races
    races = ["HUMAN", "ELF", "DRAGON", "BEASTHUMAN"]
    genders = ["BOY", "GIRL"]
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
            engine.bank.issue_loan(
                borrower, principal=100.0, holder_type="AGENT", current_tick=t
            )

        if t == 100 and len(agent_ids) > 0:
            borrower = engine.agents[agent_ids[0]]
            loans = list(engine.bank.loans.keys())
            if loans:
                engine.bank.process_loan_repayment(borrower, loans[0], installment=50.0)

    final_total = engine.bank.reserve_credits + sum(a.credits for a in engine.agents.values())
    drift = abs(final_total - initial_total)
    assert drift < 1e-4, f"Drift {drift:.6f} exceeds tolerance!"


def test_wtc_cpi_inflation_under_winter_scarcity_and_borrowing():
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


def test_property_probate_cascade_and_escheatment():
    """
    Verifies 16x16m property probate cascade:
    - Heir inheritance (spouse / children).
    - Heirless death inside settlement escheats to settlement treasury.
    - Heirless death in wilderness reverts to UNCLAIMED (None).
    """
    prop_mgr = PropertyManager()

    # 1. Register parcel in settlement "town_solis"
    p1 = ParcelRecord(
        parcel_id="10_10",
        cx=10,
        cz=10,
        owner_id="agent_alice",
        settlement_id="town_solis",
        assessed_value=200.0,
    )
    prop_mgr.register_parcel(p1)
    assert p1.owner_id == "agent_alice"
    assert p1.settlement_id == "town_solis"

    # Alice has a spouse Bob
    alice = AgentRecord(
        agent_id="agent_alice",
        slot_idx=1,
        display_name="Alice",
        dynasty_surname="Vanguard",
        gender="GIRL",
        spouse_id="agent_bob",
        stage="ADULT",
        credits=50.0,
    )
    bob = AgentRecord(
        agent_id="agent_bob",
        slot_idx=2,
        display_name="Bob",
        dynasty_surname="Vanguard",
        gender="BOY",
        stage="ADULT",
        credits=50.0,
    )
    all_agents = {"agent_alice": alice, "agent_bob": bob}

    # Alice dies -> Bob inherits via probate cascade
    results1 = prop_mgr.execute_probate_and_escheatment(deceased=alice, all_agents=all_agents)
    assert len(results1) == 1
    assert results1[0] == ("10_10", "PROBATE_HEIR", "agent_bob")
    assert prop_mgr.parcels["10_10"].owner_id == "agent_bob"

    # 2. Bob dies with NO heirs inside settlement "town_solis" -> escheats to settlement treasury
    bob.spouse_id = None
    bob.parent_ids = []
    results2 = prop_mgr.execute_probate_and_escheatment(deceased=bob, all_agents=all_agents)
    assert len(results2) == 1
    assert results2[0] == ("10_10", "ESCHEATMENT_SETTLEMENT", "town_solis")
    assert prop_mgr.parcels["10_10"].owner_id == "town_solis"

    # 3. Wilderness parcel (outside all settlements) owned by heirless hermit Charlie
    charlie = AgentRecord(
        agent_id="agent_charlie",
        slot_idx=3,
        display_name="Charlie",
        dynasty_surname="Wilder",
        gender="BOY",
        stage="ADULT",
        credits=10.0,
    )
    p_wild = ParcelRecord(
        parcel_id="200_200",
        cx=200,
        cz=200,
        owner_id="agent_charlie",
        settlement_id=None,
        assessed_value=100.0,
    )
    prop_mgr.register_parcel(p_wild)

    results3 = prop_mgr.execute_probate_and_escheatment(
        deceased=charlie, all_agents={"agent_charlie": charlie}
    )
    assert len(results3) == 1
    assert results3[0] == ("200_200", "ESCHEATMENT_WILDERNESS", "UNCLAIMED")
    assert prop_mgr.parcels["200_200"].owner_id is None
