"""
tests/test_healer_resilience.py
Phase 1 Acceptance Tests:
- Auto-healing across all 6 fault classes
- Escalation Guard: 6 occurrences of the same fault class in one game day
  auto-heal the first 5 and escalate to [CRITICAL] on the 6th.
- Subsystem pause and day reset.
"""

from sim_core.resilience.healer import ErrorHealer, FaultClass


def test_healer_auto_heals_all_six_fault_classes():
    """Verifies each of the 6 fault classes is successfully auto-healed on first occurrence."""
    healer = ErrorHealer()
    day = 1
    tick = 100

    faults: list[tuple[FaultClass, dict]] = [
        ("TENSOR_NAN_INF", {"slot_idx": 42}),
        ("ECONOMY_CONSERVATION_DRIFT", {"amount": 50.0}),
        ("COORD_OUT_OF_BOUNDS", {"x": 99999.0, "z": -99999.0}),
        ("WS_BRIDGE_DROP", {}),
        ("SQLITE_COMMIT_FAIL", {}),
        ("AGENT_REPEAT_FAULT", {}),
    ]

    for fault_class, ctx in faults:
        result = healer.handle(
            fault_class=fault_class,
            day=day,
            tick=tick,
            agent_id="agt_test",
            context=ctx,
        )
        assert result.healed is True
        assert result.escalated is False
        assert result.alert_message is None
        assert len(result.action_taken) > 0

    assert len(healer.incidents) == 6
    assert len(healer.paused_subsystems) == 0


def test_healer_escalation_guard_on_sixth_fault():
    """
    Acceptance Requirement:
    Triggering the exact same fault_class 6 times in 1 day auto-heals the first 5
    and escalates to [CRITICAL] on the 6th.
    """
    healer = ErrorHealer()
    day = 1
    fault_class: FaultClass = "TENSOR_NAN_INF"

    # First 5 occurrences must auto-heal cleanly
    for i in range(1, 6):
        res = healer.handle(
            fault_class=fault_class,
            day=day,
            tick=i * 10,
            agent_id=f"agt_{i}",
            context={"slot_idx": i},
        )
        assert res.healed is True, f"Occurrence {i} must be auto-healed"
        assert res.escalated is False
        assert res.alert_message is None
        assert healer.get_fault_count(day, fault_class) == i

    assert "neural_engine" not in healer.paused_subsystems

    # 6th occurrence must escalate to [CRITICAL]
    res_6th = healer.handle(
        fault_class=fault_class,
        day=day,
        tick=60,
        agent_id="agt_6",
        context={"slot_idx": 6},
    )

    assert res_6th.healed is False, "6th occurrence must NOT be silently auto-healed"
    assert res_6th.escalated is True, "6th occurrence must escalate to CRITICAL"
    assert res_6th.alert_message is not None
    assert "[CRITICAL_ESCALATION]" in res_6th.alert_message
    assert "neural_engine" in healer.paused_subsystems


def test_healer_day_rollover_resets_escalation_counter():
    """Verifies that crossing into a new game day resets the 5-fault threshold."""
    healer = ErrorHealer()
    fault_class: FaultClass = "COORD_OUT_OF_BOUNDS"

    # Trigger 5 faults on Day 1
    for i in range(1, 6):
        res = healer.handle(
            fault_class=fault_class,
            day=1,
            tick=i * 5,
            context={"x": 6000.0, "z": 6000.0},
        )
        assert res.healed is True
        assert res.escalated is False

    # Rollover to Day 2
    healer.reset_day(new_day=2)

    # First fault on Day 2 should auto-heal cleanly
    res_day2 = healer.handle(
        fault_class=fault_class,
        day=2,
        tick=10810,
        context={"x": 7000.0, "z": 7000.0},
    )
    assert res_day2.healed is True
    assert res_day2.escalated is False
    assert healer.get_fault_count(2, fault_class) == 1
