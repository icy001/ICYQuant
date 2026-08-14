"""Tests for the execution intent boundary."""

from services.strategy.execution.boundary import (
    ExecutionIntentBoundary,
    InMemoryIntentStore,
)
from services.strategy.execution.context import ExecutionContext
from services.strategy.execution.intent import StrategySignal
from services.strategy.execution.session import StrategyExecutionSession
from services.strategy.execution.validator import IntentValidator
from services.strategy.readiness.execution_gate import ExecutionReadinessGate


def make_context(**overrides) -> ExecutionContext:
    fields = {
        "strategy_id": "STRAT-001",
        "lifecycle_state": "RUNNING",
        "runtime_state": "RUNNING",
        "readiness_state": "READY",
        "risk_state": "ALLOWED",
        "execution_state": "CONNECTED",
        "market_timestamp": 999.0,
        "timestamp": 1000.0,
    }
    fields.update(overrides)
    return ExecutionContext(**fields)


def make_signal(**overrides) -> StrategySignal:
    fields = {
        "signal_id": "SIG-001",
        "strategy_id": "STRAT-001",
        "symbol": "NVDA",
        "side": "BUY",
        "quantity": 100.0,
    }
    fields.update(overrides)
    return StrategySignal(**fields)


def make_boundary(session=None) -> ExecutionIntentBoundary:
    return ExecutionIntentBoundary(
        readiness_gate=ExecutionReadinessGate(),
        validator=IntentValidator(),
        intent_store=InMemoryIntentStore(),
        session=session,
    )


def make_active_session() -> StrategyExecutionSession:
    session = StrategyExecutionSession("STRAT-001", now=1000.0)
    session.activate()
    return session


def test_active_session_accepts_intent() -> None:
    session = make_active_session()
    boundary = make_boundary(session)
    result = boundary.create_intent(make_signal(), make_context())
    assert result.accepted is True
    assert result.state == "PENDING"
    assert result.reason is None
    assert result.intent_id.startswith("INTENT-")
    assert session.intent_count == 1


def test_paused_session_rejects_intent() -> None:
    session = make_active_session()
    session.pause()
    boundary = make_boundary(session)
    result = boundary.create_intent(make_signal(), make_context())
    assert result.accepted is False
    assert result.state == "REJECTED"
    assert result.reason == "session_not_active"
    assert session.intent_count == 0


def test_blocked_readiness_rejects_intent() -> None:
    session = make_active_session()
    boundary = make_boundary(session)
    result = boundary.create_intent(
        make_signal(),
        make_context(readiness_state="BLOCKED"),
    )
    assert result.accepted is False
    assert result.state == "REJECTED"
    assert result.reason == "readiness_blocked"


def test_risk_blocked_rejects_intent() -> None:
    session = make_active_session()
    boundary = make_boundary(session)
    result = boundary.create_intent(
        make_signal(),
        make_context(risk_state="BLOCKED"),
    )
    assert result.accepted is False
    assert result.state == "REJECTED"


def test_stale_market_data_rejects_intent() -> None:
    gate = ExecutionReadinessGate()
    stale_context = make_context(market_timestamp=900.0)
    readiness = gate.evaluate(stale_context)
    assert "market_data" in readiness.reasons

    session = make_active_session()
    boundary = make_boundary(session)
    result = boundary.create_intent(make_signal(), stale_context)
    assert result.accepted is False


def test_expired_readiness_verdict_rejects_intent() -> None:
    # The previous READY verdict is 100s old but max readiness age is 5s.
    session = make_active_session()
    boundary = make_boundary(session)
    result = boundary.create_intent(
        make_signal(),
        make_context(readiness_checked_at=900.0),
    )
    assert result.accepted is False
    assert result.reason == "readiness_blocked"


def test_duplicate_signal_does_not_create_second_intent() -> None:
    session = make_active_session()
    boundary = make_boundary(session)
    first = boundary.create_intent(make_signal(), make_context())
    second = boundary.create_intent(make_signal(), make_context())
    assert first.accepted is True
    assert first.intent_id == second.intent_id
    assert second.reason == "duplicate"
    assert len(boundary.intent_store) == 1
    assert session.intent_count == 1


def test_validation_failure_rejects_intent() -> None:
    session = make_active_session()
    boundary = make_boundary(session)
    result = boundary.create_intent(
        make_signal(side="LONG"),
        make_context(),
    )
    assert result.accepted is False
    assert result.state == "REJECTED"
    assert "side" in result.reason


def test_duplicate_detection_uses_fingerprint_not_signal_id() -> None:
    session = make_active_session()
    boundary = make_boundary(session)
    first = boundary.create_intent(
        make_signal(),
        make_context(),
        execution_policy="TWAP",
    )
    second = boundary.create_intent(
        make_signal(),
        make_context(),
        execution_policy="LIMIT",
    )
    assert first.accepted is True
    assert second.accepted is True
    assert first.intent_id != second.intent_id
    assert len(boundary.intent_store) == 2


def test_boundary_works_without_bound_session() -> None:
    boundary = make_boundary(session=None)
    result = boundary.create_intent(make_signal(), make_context())
    assert result.accepted is True
    assert result.state == "PENDING"
