"""Tests for the guarded, idempotent risk handoff."""

from datetime import datetime
from typing import Any

import pytest

from services.strategy.execution.context import ExecutionContext
from services.strategy.execution.handoff import (
    HANDOFF_EVENTS,
    RiskHandoff,
    new_decision_id,
)
from services.strategy.execution.intent import ExecutionIntent
from services.strategy.execution.lifecycle import IntentLifecycle
from services.strategy.readiness.execution_gate import ExecutionReadinessGate


def make_context(**overrides) -> ExecutionContext:
    fields = {
        "strategy_id": "STRAT-001",
        "lifecycle_state": "RUNNING",
        "runtime_state": "RUNNING",
        "readiness_state": "READY",
        "risk_state": "ALLOWED",
        "execution_state": "CONNECTED",
        "session_state": "ACTIVE",
        "market_timestamp": 999.0,
        "readiness_checked_at": 999.0,
        "timestamp": 1000.0,
    }
    fields.update(overrides)
    return ExecutionContext(**fields)


def make_intent(**overrides) -> ExecutionIntent:
    fields = {
        "intent_id": "INTENT-20260813-000001",
        "strategy_id": "STRAT-001",
        "session_id": "SESSION-STRAT001-20260813-01",
        "signal_id": "SIG-001",
        "correlation_id": "CORR-20260813-000001",
        "symbol": "NVDA",
        "side": "BUY",
        "target_quantity": 100.0,
        "execution_policy": "MARKET",
        "urgency": "NORMAL",
        "state": "VALIDATED",
        "created_at": 1000.0,
        "market_timestamp": 999.0,
        "expires_at": 1005.0,
    }
    fields.update(overrides)
    return ExecutionIntent(**fields)


def make_handoff(**kwargs) -> RiskHandoff:
    return RiskHandoff(ExecutionReadinessGate(), **kwargs)


# --- valid handoff --------------------------------------------------------


def test_valid_handoff_is_accepted() -> None:
    handoff = make_handoff(clock=1001.0)
    result = handoff.submit(make_intent(), make_context())
    assert result.accepted is True
    assert result.state == "SUBMITTED"
    assert result.reason is None
    assert result.decision_id is not None
    assert result.decision_id.startswith("RISK-")


def test_decision_id_shape() -> None:
    decision_id = new_decision_id(1775000000.0)
    date_part = datetime.fromtimestamp(1775000000.0).strftime("%Y%m%d")
    assert decision_id.startswith("RISK-%s-" % date_part)


# --- gate: SessionActive --------------------------------------------------


def test_closed_session_blocks_handoff() -> None:
    handoff = make_handoff(clock=1001.0)
    result = handoff.submit(
        make_intent(),
        make_context(session_state="CLOSED"),
    )
    assert result.accepted is False
    assert result.state == "REJECTED"
    assert result.reason == "session_not_active"
    assert result.decision_id is None


def test_unknown_session_state_blocks_handoff() -> None:
    # fail-safe: an UNKNOWN session state can never reach the risk engine
    handoff = make_handoff(clock=1001.0)
    result = handoff.submit(
        make_intent(),
        make_context(session_state="UNKNOWN"),
    )
    assert result.accepted is False
    assert result.reason == "session_not_active"


# --- gate: ReadinessReady -------------------------------------------------


def test_blocked_readiness_blocks_handoff() -> None:
    handoff = make_handoff(clock=1001.0)
    result = handoff.submit(
        make_intent(),
        make_context(readiness_state="BLOCKED"),
    )
    assert result.accepted is False
    assert result.reason == "readiness_blocked"


def test_risk_blocked_blocks_handoff() -> None:
    handoff = make_handoff(clock=1001.0)
    result = handoff.submit(
        make_intent(),
        make_context(risk_state="BLOCKED"),
    )
    assert result.accepted is False
    assert result.reason == "readiness_blocked"


def test_stale_market_data_blocks_handoff() -> None:
    handoff = make_handoff(clock=1001.0)
    result = handoff.submit(
        make_intent(),
        make_context(market_timestamp=900.0),
    )
    assert result.accepted is False
    assert result.reason == "readiness_blocked"


def test_stale_readiness_verdict_blocks_handoff() -> None:
    handoff = make_handoff(clock=1001.0)
    result = handoff.submit(
        make_intent(),
        make_context(readiness_checked_at=900.0),
    )
    assert result.accepted is False
    assert result.reason == "readiness_blocked"


# --- gate: IntentValidated / NotCancelled ---------------------------------


def test_unvalidated_intent_blocks_handoff() -> None:
    handoff = make_handoff(clock=1001.0)
    result = handoff.submit(make_intent(state="PENDING"), make_context())
    assert result.accepted is False
    assert result.reason == "intent_not_validated"


def test_cancelled_intent_blocks_handoff() -> None:
    handoff = make_handoff(clock=1001.0)
    result = handoff.submit(make_intent(state="CANCELLED"), make_context())
    assert result.accepted is False
    assert result.reason == "intent_cancelled"


def test_rejected_intent_blocks_handoff() -> None:
    handoff = make_handoff(clock=1001.0)
    result = handoff.submit(make_intent(state="REJECTED"), make_context())
    assert result.accepted is False
    assert result.reason == "intent_not_validated"


# --- gate: NotExpired -----------------------------------------------------


def test_expired_intent_blocks_handoff() -> None:
    handoff = make_handoff(clock=1006.0)  # expires_at == 1005.0
    result = handoff.submit(make_intent(), make_context())
    assert result.accepted is False
    assert result.reason == "intent_expired"


def test_handoff_at_expiry_boundary_is_accepted() -> None:
    # now == expires_at is NOT past the expiry window
    handoff = make_handoff(clock=1005.0)
    result = handoff.submit(make_intent(), make_context())
    assert result.accepted is True


def test_intent_without_expiry_never_expires() -> None:
    handoff = make_handoff(clock=2000.0)
    result = handoff.submit(
        make_intent(expires_at=0.0),
        make_context(timestamp=1000.0),
    )
    assert result.accepted is True


# --- idempotency ----------------------------------------------------------


def test_idempotent_replay_returns_same_decision() -> None:
    handoff = make_handoff(clock=1001.0)
    intent = make_intent()
    first = handoff.submit(intent, make_context())
    second = handoff.submit(intent, make_context())
    assert first.accepted is True
    assert second.accepted is True
    assert second.reason == "duplicate"
    assert second.decision_id == first.decision_id


def test_idempotency_prevents_double_position() -> None:
    # two submissions, one risk decision -> an event bus retry can never
    # create a doubled position
    handoff = make_handoff(clock=1001.0)
    intent = make_intent()
    first = handoff.submit(intent, make_context())
    second = handoff.submit(intent, make_context())
    assert len(handoff.decisions) == 1
    assert first.decision_id == second.decision_id
    assert handoff.decisions[intent.intent_id] == first.decision_id


def test_different_intents_get_different_decisions() -> None:
    handoff = make_handoff(clock=1001.0)
    first = handoff.submit(
        make_intent(intent_id="INTENT-20260813-000001"),
        make_context(),
    )
    second = handoff.submit(
        make_intent(intent_id="INTENT-20260813-000002"),
        make_context(),
    )
    assert first.decision_id != second.decision_id
    assert len(handoff.decisions) == 2


# --- lifecycle integration -------------------------------------------------


def test_lifecycle_advanced_on_acceptance() -> None:
    handoff = make_handoff(clock=1001.0)
    lifecycle = IntentLifecycle("INTENT-20260813-000001", state="VALIDATED")
    result = handoff.submit(make_intent(), make_context(), lifecycle=lifecycle)
    assert result.accepted is True
    assert lifecycle.state == "SUBMITTED"


# --- events ---------------------------------------------------------------


def test_handoff_emits_submitted_and_accepted() -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    handoff = make_handoff(
        clock=1001.0,
        emit=lambda event, payload: events.append((event, payload)),
    )
    handoff.submit(make_intent(), make_context())
    handoff.submit(make_intent(), make_context())  # idempotent replay
    names = [event for event, _ in events]
    assert names == [
        HANDOFF_EVENTS["submitted"],
        HANDOFF_EVENTS["accepted"],
        HANDOFF_EVENTS["submitted"],
        HANDOFF_EVENTS["duplicate"],
    ]


def test_rejected_handoff_emits_rejected_event() -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    handoff = make_handoff(
        clock=1001.0,
        emit=lambda event, payload: events.append((event, payload)),
    )
    handoff.submit(make_intent(), make_context(session_state="CLOSED"))
    names = [event for event, _ in events]
    assert names == [
        HANDOFF_EVENTS["submitted"],
        HANDOFF_EVENTS["rejected"],
    ]


def test_accepted_payload_carries_audit_fields() -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    handoff = make_handoff(
        clock=1001.0,
        emit=lambda event, payload: events.append((event, payload)),
    )
    handoff.submit(make_intent(), make_context())
    _, payload = events[1]
    assert payload["event"] == HANDOFF_EVENTS["accepted"]
    assert payload["strategy_id"] == "STRAT-001"
    assert payload["intent_id"] == "INTENT-20260813-000001"
    assert payload["session_id"] == "SESSION-STRAT001-20260813-01"
    assert payload["signal_id"] == "SIG-001"
    assert payload["correlation_id"] == "CORR-20260813-000001"
    assert payload["symbol"] == "NVDA"
    assert payload["side"] == "BUY"
    assert payload["target_quantity"] == 100.0
    assert payload["session_state"] == "ACTIVE"
    assert payload["timestamp"] == 1001.0
    assert payload["decision_id"] is not None


# --- request artifact -----------------------------------------------------


def test_last_request_carries_frozen_snapshot() -> None:
    handoff = make_handoff(clock=1001.0)
    handoff.submit(make_intent(), make_context())
    assert handoff.last_request is not None
    assert handoff.last_request.submitted_at == 1001.0
    assert handoff.last_request.snapshot.intent_id == "INTENT-20260813-000001"
    assert handoff.last_request.snapshot.state == "VALIDATED"
    assert handoff.last_request.snapshot.correlation_id == (
        "CORR-20260813-000001"
    )


# --- malformed input ------------------------------------------------------


def test_missing_intent_id_raises() -> None:
    handoff = make_handoff(clock=1001.0)
    with pytest.raises(ValueError):
        handoff.submit(make_intent(intent_id=""), make_context())
