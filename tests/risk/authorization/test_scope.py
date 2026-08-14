"""Tests for the authorization scope."""

from dataclasses import FrozenInstanceError

import pytest

from services.risk.authorization.certificate import ExecutionAuthorizationCertificate
from services.risk.authorization.scope import (
    AuthorizationScope,
    scope_from_certificate,
    scope_from_decision,
)
from services.risk.authorization.decision import approved_decision


def make_certificate(**overrides) -> ExecutionAuthorizationCertificate:
    fields = {
        "certificate_id": "CERT-001",
        "authorization_id": "AUTH-001",
        "decision_id": "RISK-001",
        "intent_id": "INT-001",
        "strategy_id": "STRAT-001",
        "session_id": "SESSION-001",
        "signal_id": "SIG-001",
        "correlation_id": "CORR-001",
        "approved": True,
        "approved_quantity": 100.0,
        "issued_at": 1000.0,
        "expires_at": 1005.0,
        "symbol": "NVDA",
        "side": "BUY",
        "execution_policy": "LIMIT",
    }
    fields.update(overrides)
    return ExecutionAuthorizationCertificate(**fields)


def test_scope_holds_authorization_boundary() -> None:
    scope = AuthorizationScope(
        strategy_id="STRAT-001",
        session_id="SESSION-001",
        signal_id="SIG-001",
        intent_id="INT-001",
        symbol="NVDA",
        side="BUY",
        approved_quantity=100.0,
    )
    assert scope.strategy_id == "STRAT-001"
    assert scope.session_id == "SESSION-001"
    assert scope.signal_id == "SIG-001"
    assert scope.intent_id == "INT-001"
    assert scope.symbol == "NVDA"
    assert scope.side == "BUY"
    assert scope.approved_quantity == 100.0


def test_scope_is_frozen() -> None:
    scope = AuthorizationScope(
        strategy_id="STRAT-001",
        session_id="SESSION-001",
        signal_id="SIG-001",
        intent_id="INT-001",
        symbol="NVDA",
        side="BUY",
        approved_quantity=100.0,
    )
    with pytest.raises(FrozenInstanceError):
        scope.approved_quantity = 500.0  # type: ignore[misc]


def test_scope_from_certificate() -> None:
    scope = scope_from_certificate(make_certificate())
    assert scope.strategy_id == "STRAT-001"
    assert scope.session_id == "SESSION-001"
    assert scope.signal_id == "SIG-001"
    assert scope.intent_id == "INT-001"
    assert scope.symbol == "NVDA"
    assert scope.side == "BUY"
    assert scope.approved_quantity == 100.0


def test_scope_from_decision() -> None:
    decision = approved_decision(
        intent_id="INT-001",
        strategy_id="STRAT-001",
        session_id="SESSION-001",
        signal_id="SIG-001",
        correlation_id="CORR-001",
        symbol="NVDA",
        side="BUY",
        approved_quantity=100.0,
        decided_at=999.0,
    )
    scope = scope_from_decision(decision)
    assert scope.intent_id == "INT-001"
    assert scope.symbol == "NVDA"
    assert scope.side == "BUY"
    assert scope.approved_quantity == 100.0


def test_scope_as_dict() -> None:
    mapping = scope_from_certificate(make_certificate()).as_dict()
    assert mapping["strategy_id"] == "STRAT-001"
    assert mapping["intent_id"] == "INT-001"
    assert mapping["symbol"] == "NVDA"
    assert mapping["side"] == "BUY"
    assert mapping["approved_quantity"] == 100.0
