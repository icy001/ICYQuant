"""Tests for the risk authorization contracts."""

from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from services.risk.authorization.contract import (
    ExecutionAuthorization,
    RiskAuthorizationRequest,
    authorization_from_decision,
    new_authorization_id,
    new_request_id,
)
from services.risk.authorization.decision import approved_decision
from services.strategy.execution.snapshot import IntentSnapshot


def make_snapshot(**overrides) -> IntentSnapshot:
    fields = {
        "intent_id": "INTENT-20260813-000001",
        "strategy_id": "STRAT-001",
        "session_id": "SESSION-001",
        "signal_id": "SIG-001",
        "correlation_id": "CORR-001",
        "symbol": "NVDA",
        "side": "BUY",
        "target_quantity": 100.0,
        "execution_policy": "LIMIT",
        "urgency": "NORMAL",
        "state": "VALIDATED",
        "created_at": 1000.0,
        "expires_at": 1005.0,
        "captured_at": 1001.0,
    }
    fields.update(overrides)
    return IntentSnapshot(**fields)


def test_authorization_request_from_snapshot() -> None:
    request = RiskAuthorizationRequest.from_snapshot(
        make_snapshot(),
        submitted_at=1001.0,
    )
    assert request.request_id.startswith("RAUTH-")
    assert request.intent_id == "INTENT-20260813-000001"
    assert request.strategy_id == "STRAT-001"
    assert request.session_id == "SESSION-001"
    assert request.signal_id == "SIG-001"
    assert request.correlation_id == "CORR-001"
    assert request.symbol == "NVDA"
    assert request.side == "BUY"
    assert request.target_quantity == 100.0
    assert request.execution_policy == "LIMIT"
    assert request.urgency == "NORMAL"
    assert request.submitted_at == 1001.0


def test_authorization_request_is_frozen() -> None:
    request = RiskAuthorizationRequest.from_snapshot(
        make_snapshot(),
        submitted_at=1001.0,
    )
    with pytest.raises(FrozenInstanceError):
        request.target_quantity = 999.0  # type: ignore[misc]


def test_authorization_request_requires_correlation_id() -> None:
    with pytest.raises(ValueError):
        RiskAuthorizationRequest.from_snapshot(
            make_snapshot(correlation_id=None),
            submitted_at=1001.0,
        )


def test_execution_authorization_fields() -> None:
    authorization = authorization_from_decision(
        approved_decision(decided_at=999.0),
        authorization_id="AUTH-001",
        granted_at=1000.0,
    )
    assert authorization.authorization_id == "AUTH-001"
    assert authorization.decision_id.startswith("RISK-")
    assert authorization.intent_id == "INT-001"
    assert authorization.approved is True
    assert authorization.approved_quantity == 100.0
    assert authorization.granted_at == 1000.0


def test_execution_authorization_is_frozen() -> None:
    authorization = authorization_from_decision(approved_decision(decided_at=999.0))
    with pytest.raises(FrozenInstanceError):
        authorization.approved_quantity = 500.0  # type: ignore[misc]


def test_authorization_from_decision_preserves_lineage() -> None:
    decision = approved_decision(decided_at=999.0)
    authorization = authorization_from_decision(decision, granted_at=999.0)
    assert authorization.decision_id == decision.decision_id
    assert authorization.intent_id == decision.intent_id
    assert authorization.strategy_id == decision.strategy_id
    assert authorization.correlation_id == decision.correlation_id


def test_new_authorization_id_shape() -> None:
    authorization_id = new_authorization_id(1775000000.0)
    date_part = datetime.fromtimestamp(1775000000.0).strftime("%Y%m%d")
    assert authorization_id.startswith(f"AUTH-{date_part}-")


def test_new_request_id_shape() -> None:
    request_id = new_request_id(1775000000.0)
    date_part = datetime.fromtimestamp(1775000000.0).strftime("%Y%m%d")
    assert request_id.startswith(f"RAUTH-{date_part}-")
