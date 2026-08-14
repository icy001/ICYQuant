"""Tests for the execution intent model."""

import dataclasses
from datetime import datetime

import pytest

from services.strategy.execution.intent import (
    SUPPORTED_EXECUTION_POLICIES,
    SUPPORTED_SIDES,
    SUPPORTED_URGENCIES,
    ExecutionIntent,
    ExecutionIntentState,
    StrategySignal,
    intent_fingerprint,
    intent_state_value,
    is_terminal,
    new_intent_id,
)


def make_signal(**overrides) -> StrategySignal:
    fields = {
        "signal_id": "SIG-001",
        "strategy_id": "STRAT-001",
        "symbol": "NVDA",
        "side": "BUY",
        "quantity": 100.0,
        "confidence": 0.87,
        "metadata": {"reason_code": "MOMENTUM_BREAKOUT"},
    }
    fields.update(overrides)
    return StrategySignal(**fields)


def make_intent(**overrides) -> ExecutionIntent:
    fields = {
        "intent_id": "INTENT-20260813-000001",
        "strategy_id": "STRAT-001",
        "signal_id": "SIG-001",
        "symbol": "NVDA",
        "side": "BUY",
        "target_quantity": 100.0,
        "execution_policy": "TWAP",
        "urgency": "NORMAL",
    }
    fields.update(overrides)
    return ExecutionIntent(**fields)


def test_intent_state_values() -> None:
    assert ExecutionIntentState.PENDING.value == "PENDING"
    assert ExecutionIntentState.VALIDATED.value == "VALIDATED"
    assert ExecutionIntentState.SUBMITTED.value == "SUBMITTED"
    assert ExecutionIntentState.REJECTED.value == "REJECTED"
    assert ExecutionIntentState.EXPIRED.value == "EXPIRED"
    assert ExecutionIntentState.CANCELLED.value == "CANCELLED"


def test_new_intent_id_has_expected_format() -> None:
    timestamp = 1775000000.0
    expected_date = datetime.fromtimestamp(timestamp).strftime("%Y%m%d")
    intent_id = new_intent_id(timestamp)
    assert intent_id.startswith("INTENT-%s-" % expected_date)
    assert intent_id.rsplit("-", 1)[-1].isdigit()


def test_new_intent_ids_are_unique() -> None:
    first = new_intent_id(1775000000.0)
    second = new_intent_id(1775000000.0)
    assert first != second


def test_intent_fingerprint_is_deterministic() -> None:
    first = intent_fingerprint(
        strategy_id="STRAT-001",
        signal_id="SIG-001",
        symbol="NVDA",
        side="BUY",
        target_quantity=100.0,
        execution_policy="TWAP",
    )
    second = intent_fingerprint(
        strategy_id="STRAT-001",
        signal_id="SIG-001",
        symbol="NVDA",
        side="BUY",
        target_quantity=100.0,
        execution_policy="TWAP",
    )
    assert first == second
    assert len(first) == 64


def test_intent_fingerprint_is_sensitive_to_fields() -> None:
    base = intent_fingerprint(
        strategy_id="STRAT-001",
        signal_id="SIG-001",
        symbol="NVDA",
        side="BUY",
        target_quantity=100.0,
        execution_policy="TWAP",
    )
    other_side = intent_fingerprint(
        strategy_id="STRAT-001",
        signal_id="SIG-001",
        symbol="NVDA",
        side="SELL",
        target_quantity=100.0,
        execution_policy="TWAP",
    )
    other_quantity = intent_fingerprint(
        strategy_id="STRAT-001",
        signal_id="SIG-001",
        symbol="NVDA",
        side="BUY",
        target_quantity=200.0,
        execution_policy="TWAP",
    )
    assert base != other_side
    assert base != other_quantity


def test_signal_carries_no_broker_details() -> None:
    signal = make_signal()
    assert not hasattr(signal, "broker_order_id")
    assert not hasattr(signal, "exchange_order_id")
    assert not hasattr(signal, "broker_account")
    assert not hasattr(signal, "fix_session")
    assert not hasattr(signal, "broker_route")


def test_strategy_intent_contains_no_broker_details() -> None:
    intent = make_intent()
    assert not hasattr(intent, "broker_order_id")
    assert not hasattr(intent, "exchange_order_id")
    assert not hasattr(intent, "broker_account")
    assert not hasattr(intent, "fix_session")
    assert not hasattr(intent, "broker_route")


def test_intent_is_frozen() -> None:
    intent = make_intent()
    with pytest.raises(dataclasses.FrozenInstanceError):
        intent.side = "SELL"


def test_intent_carries_lineage() -> None:
    intent = make_intent(
        session_id="SESSION-STRAT001-20260813-01",
        correlation_id="CORR-1",
        intent_fingerprint="deadbeef",
        created_at=100.0,
        market_timestamp=98.0,
        expires_at=102.0,
    )
    assert intent.strategy_id == "STRAT-001"
    assert intent.session_id == "SESSION-STRAT001-20260813-01"
    assert intent.signal_id == "SIG-001"
    assert intent.intent_id == "INTENT-20260813-000001"
    assert intent.correlation_id == "CORR-1"


def test_state_helpers() -> None:
    assert intent_state_value(ExecutionIntentState.PENDING) == "PENDING"
    assert intent_state_value("PENDING") == "PENDING"
    assert is_terminal(ExecutionIntentState.REJECTED) is True
    assert is_terminal(ExecutionIntentState.EXPIRED) is True
    assert is_terminal(ExecutionIntentState.CANCELLED) is True
    assert is_terminal(ExecutionIntentState.PENDING) is False
    assert is_terminal("SUBMITTED") is False


def test_supported_enums() -> None:
    assert SUPPORTED_SIDES == frozenset({"BUY", "SELL"})
    assert SUPPORTED_EXECUTION_POLICIES == frozenset(
        {"MARKET", "LIMIT", "TWAP", "VWAP", "PASSIVE"}
    )
    assert SUPPORTED_URGENCIES == frozenset({"LOW", "NORMAL", "HIGH", "CRITICAL"})
