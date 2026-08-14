"""Tests for the frozen intent snapshot."""

import pytest

from services.strategy.execution.intent import ExecutionIntent
from services.strategy.execution.snapshot import (
    IntentSnapshot,
    snapshot_intent,
)


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
        "expires_at": 1002.0,
    }
    fields.update(overrides)
    return ExecutionIntent(**fields)


def test_snapshot_freezes_intent_fields() -> None:
    snapshot = snapshot_intent(make_intent(), captured_at=1001.0)
    assert snapshot.intent_id == "INTENT-20260813-000001"
    assert snapshot.strategy_id == "STRAT-001"
    assert snapshot.session_id == "SESSION-STRAT001-20260813-01"
    assert snapshot.signal_id == "SIG-001"
    assert snapshot.correlation_id == "CORR-20260813-000001"
    assert snapshot.symbol == "NVDA"
    assert snapshot.side == "BUY"
    assert snapshot.target_quantity == 100.0
    assert snapshot.execution_policy == "MARKET"
    assert snapshot.urgency == "NORMAL"
    assert snapshot.state == "VALIDATED"
    assert snapshot.created_at == 1000.0
    assert snapshot.expires_at == 1002.0
    assert snapshot.captured_at == 1001.0


def test_snapshot_is_immutable() -> None:
    snapshot = snapshot_intent(make_intent(), captured_at=1001.0)
    with pytest.raises(AttributeError):
        snapshot.state = "SUBMITTED"
    assert snapshot.state == "VALIDATED"


def test_snapshot_captured_at_defaults_to_now() -> None:
    snapshot = snapshot_intent(make_intent())
    assert snapshot.captured_at > 0


def test_snapshot_copies_metadata() -> None:
    intent = make_intent(metadata={"source": "research"})
    snapshot = snapshot_intent(intent, captured_at=1001.0)
    assert snapshot.metadata == {"source": "research"}


def test_snapshot_as_dict() -> None:
    snapshot = snapshot_intent(make_intent(), captured_at=1001.0)
    data = snapshot.as_dict()
    assert data["intent_id"] == "INTENT-20260813-000001"
    assert data["correlation_id"] == "CORR-20260813-000001"
    assert data["state"] == "VALIDATED"
    assert data["captured_at"] == 1001.0
    assert len(data) == 14


def test_snapshot_is_frozen_dataclass() -> None:
    snapshot = snapshot_intent(make_intent(), captured_at=1001.0)
    assert isinstance(snapshot, IntentSnapshot)
