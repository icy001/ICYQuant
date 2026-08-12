"""
Tests for RecoveryGate / RecoveryChecks (Commit 26 Part 1.5,
spec sections 16-17, 27-28).

Recovery 不能只检查"程序活着"：Service = UP 不代表 Recovery = OK。
"""

from services.control_plane.recovery import (
    RecoveryChecks,
    RecoveryGate,
    RecoveryPolicy,
)


def _all_clear() -> RecoveryChecks:
    return RecoveryChecks(
        incident_clear=True,
        positions_reconciled=True,
        orders_reconciled=True,
        risk_healthy=True,
        execution_healthy=True,
        venues_healthy=True,
        strategy_state_valid=True,
        event_stream_healthy=True,
    )


def test_recovery_requires_reconciliation():
    gate = RecoveryGate()

    checks = RecoveryChecks(
        incident_clear=True,
        positions_reconciled=False,
        orders_reconciled=True,
        risk_healthy=True,
        execution_healthy=True,
        venues_healthy=True,
        strategy_state_valid=True,
        event_stream_healthy=True,
    )

    assert not gate.validate(checks)


def test_recovery_passes_all_checks():
    gate = RecoveryGate()

    assert gate.validate(_all_clear())


def test_recovery_requires_incident_clear():
    gate = RecoveryGate()

    checks = RecoveryChecks(
        incident_clear=False,
        positions_reconciled=True,
        orders_reconciled=True,
        risk_healthy=True,
        execution_healthy=True,
        venues_healthy=True,
        strategy_state_valid=True,
        event_stream_healthy=True,
    )

    assert not gate.validate(checks)


def test_recovery_requires_orders_reconciled():
    gate = RecoveryGate()

    checks = RecoveryChecks(
        incident_clear=True,
        positions_reconciled=True,
        orders_reconciled=False,
        risk_healthy=True,
        execution_healthy=True,
        venues_healthy=True,
        strategy_state_valid=True,
        event_stream_healthy=True,
    )

    assert not gate.validate(checks)


def test_recovery_requires_risk_healthy():
    gate = RecoveryGate()

    checks = RecoveryChecks(
        incident_clear=True,
        positions_reconciled=True,
        orders_reconciled=True,
        risk_healthy=False,
        execution_healthy=True,
        venues_healthy=True,
        strategy_state_valid=True,
        event_stream_healthy=True,
    )

    assert not gate.validate(checks)


def test_recovery_requires_execution_healthy():
    gate = RecoveryGate()

    checks = RecoveryChecks(
        incident_clear=True,
        positions_reconciled=True,
        orders_reconciled=True,
        risk_healthy=True,
        execution_healthy=False,
        venues_healthy=True,
        strategy_state_valid=True,
        event_stream_healthy=True,
    )

    assert not gate.validate(checks)


def test_recovery_requires_venues_healthy():
    gate = RecoveryGate()

    checks = RecoveryChecks(
        incident_clear=True,
        positions_reconciled=True,
        orders_reconciled=True,
        risk_healthy=True,
        execution_healthy=True,
        venues_healthy=False,
        strategy_state_valid=True,
        event_stream_healthy=True,
    )

    assert not gate.validate(checks)


def test_recovery_requires_strategy_state_valid():
    gate = RecoveryGate()

    checks = RecoveryChecks(
        incident_clear=True,
        positions_reconciled=True,
        orders_reconciled=True,
        risk_healthy=True,
        execution_healthy=True,
        venues_healthy=True,
        strategy_state_valid=False,
        event_stream_healthy=True,
    )

    assert not gate.validate(checks)


def test_recovery_requires_event_stream_healthy():
    gate = RecoveryGate()

    checks = RecoveryChecks(
        incident_clear=True,
        positions_reconciled=True,
        orders_reconciled=True,
        risk_healthy=True,
        execution_healthy=True,
        venues_healthy=True,
        strategy_state_valid=True,
        event_stream_healthy=False,
    )

    assert not gate.validate(checks)


def test_requirements_can_be_relaxed_via_policy():
    """policy 可以跳过部分要求（例如位置对账不可用时也允许恢复）。"""
    gate = RecoveryGate(
        policy=RecoveryPolicy(
            require_position_reconciled=False,
        ),
    )

    checks = RecoveryChecks(
        incident_clear=True,
        positions_reconciled=False,
        orders_reconciled=True,
        risk_healthy=True,
        execution_healthy=True,
        venues_healthy=True,
        strategy_state_valid=True,
        event_stream_healthy=True,
    )

    assert gate.validate(checks)


def test_strategy_and_event_checks_are_always_required():
    """strategy_state_valid 与 event_stream_healthy 不受 policy 配置影响。"""
    gate = RecoveryGate(
        policy=RecoveryPolicy(
            require_position_reconciled=False,
            require_orders_reconciled=False,
            require_risk_healthy=False,
            require_execution_healthy=False,
            require_venue_healthy=False,
            require_no_open_incident=False,
        ),
    )

    assert gate.validate(_all_clear())

    broken_strategy = RecoveryChecks(
        incident_clear=True,
        positions_reconciled=True,
        orders_reconciled=True,
        risk_healthy=True,
        execution_healthy=True,
        venues_healthy=True,
        strategy_state_valid=False,
        event_stream_healthy=True,
    )
    assert not gate.validate(broken_strategy)

    broken_events = RecoveryChecks(
        incident_clear=True,
        positions_reconciled=True,
        orders_reconciled=True,
        risk_healthy=True,
        execution_healthy=True,
        venues_healthy=True,
        strategy_state_valid=True,
        event_stream_healthy=False,
    )
    assert not gate.validate(broken_events)
