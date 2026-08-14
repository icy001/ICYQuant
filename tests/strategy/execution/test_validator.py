"""Tests for the intent validator."""

import pytest

from services.strategy.execution.context import ExecutionContext
from services.strategy.execution.intent import (
    ExecutionIntent,
    ExecutionIntentState,
    StrategySignal,
)
from services.strategy.execution.validator import (
    IntentValidationError,
    IntentValidator,
)


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


def test_valid_intent_is_pending_with_ttl() -> None:
    validator = IntentValidator(ttl_seconds=2.0)
    intent = validator.validate(
        make_signal(),
        make_context(),
        execution_policy="TWAP",
        urgency="HIGH",
    )
    assert intent.state == ExecutionIntentState.PENDING.value
    assert intent.intent_id.startswith("INTENT-")
    assert intent.created_at == 1000.0
    assert intent.market_timestamp == 999.0
    assert intent.expires_at == 1002.0
    assert intent.execution_policy == "TWAP"
    assert intent.urgency == "HIGH"
    assert len(intent.intent_fingerprint) == 64


def test_validator_sets_lineage() -> None:
    validator = IntentValidator()
    intent = validator.validate(
        make_signal(),
        make_context(),
        session_id="SESSION-STRAT001-20260813-01",
        correlation_id="CORR-1",
    )
    assert intent.session_id == "SESSION-STRAT001-20260813-01"
    assert intent.correlation_id == "CORR-1"


def test_invalid_side_rejected() -> None:
    validator = IntentValidator()
    with pytest.raises(IntentValidationError):
        validator.validate(make_signal(side="LONG"), make_context())


def test_zero_or_negative_quantity_rejected() -> None:
    validator = IntentValidator()
    with pytest.raises(IntentValidationError):
        validator.validate(make_signal(quantity=0), make_context())
    with pytest.raises(IntentValidationError):
        validator.validate(make_signal(quantity=-5), make_context())


def test_missing_signal_id_rejected() -> None:
    validator = IntentValidator()
    with pytest.raises(IntentValidationError):
        validator.validate(make_signal(signal_id=""), make_context())


def test_strategy_mismatch_rejected() -> None:
    validator = IntentValidator()
    with pytest.raises(IntentValidationError):
        validator.validate(make_signal(strategy_id="STRAT-002"), make_context())


def test_invalid_execution_policy_rejected() -> None:
    validator = IntentValidator()
    with pytest.raises(IntentValidationError):
        validator.validate(make_signal(), make_context(), execution_policy="IOC")


def test_invalid_urgency_rejected() -> None:
    validator = IntentValidator()
    with pytest.raises(IntentValidationError):
        validator.validate(make_signal(), make_context(), urgency="URGENT")


def test_non_ready_context_rejected() -> None:
    validator = IntentValidator()
    with pytest.raises(IntentValidationError):
        validator.validate(
            make_signal(),
            make_context(readiness_state="BLOCKED"),
        )


def test_expired_intent() -> None:
    validator = IntentValidator()
    intent = validator.validate(make_signal(), make_context(), now=100.0)
    # default ttl 2.0 -> expires_at == 102.0
    assert validator.is_expired(intent, now=103.0) is True
    assert validator.is_expired(intent, now=101.0) is False


def test_intent_without_expiry_never_expires() -> None:
    validator = IntentValidator()
    intent = ExecutionIntent(
        intent_id="INTENT-20260813-000001",
        strategy_id="STRAT-001",
        signal_id="SIG-001",
        symbol="NVDA",
        side="BUY",
        target_quantity=100.0,
        execution_policy="MARKET",
        urgency="NORMAL",
        expires_at=0.0,
    )
    assert validator.is_expired(intent, now=200.0) is False


def test_negative_ttl_rejected() -> None:
    with pytest.raises(ValueError):
        IntentValidator(ttl_seconds=0)
