"""Tests for the immutable risk decision."""

from dataclasses import FrozenInstanceError

import pytest

from services.risk.authorization.decision import (
    RiskDecision,
    approved_decision,
    new_decision_id,
    rejected_decision,
)


def test_approved_decision_holds_fields() -> None:
    decision = approved_decision(
        intent_id="INT-001",
        strategy_id="STRAT-001",
        session_id="SESSION-001",
        signal_id="SIG-001",
        correlation_id="CORR-001",
        symbol="NVDA",
        side="BUY",
        approved_quantity=100.0,
        execution_policy="LIMIT",
        decided_at=999.0,
    )
    assert decision.decision_id.startswith("RISK-")
    assert decision.intent_id == "INT-001"
    assert decision.strategy_id == "STRAT-001"
    assert decision.session_id == "SESSION-001"
    assert decision.signal_id == "SIG-001"
    assert decision.correlation_id == "CORR-001"
    assert decision.approved is True
    assert decision.approved_quantity == 100.0
    assert decision.symbol == "NVDA"
    assert decision.side == "BUY"
    assert decision.execution_policy == "LIMIT"
    assert decision.decided_at == 999.0


def test_rejected_decision_is_not_approved() -> None:
    decision = rejected_decision(reason="exposure limit breached")
    assert decision.approved is False
    assert decision.approved_quantity is None
    assert decision.reason == "exposure limit breached"


def test_decision_is_frozen() -> None:
    decision = approved_decision()
    with pytest.raises(FrozenInstanceError):
        decision.approved_quantity = 999.0  # type: ignore[misc]


def test_decision_rejects_missing_identity_ids() -> None:
    with pytest.raises(ValueError):
        RiskDecision(
            decision_id="",
            intent_id="INT-001",
            strategy_id="STRAT-001",
            session_id="SESSION-001",
            signal_id="SIG-001",
            correlation_id="CORR-001",
            approved=True,
            approved_quantity=100.0,
        )
    with pytest.raises(ValueError):
        RiskDecision(
            decision_id="RISK-001",
            intent_id="",
            strategy_id="STRAT-001",
            session_id="SESSION-001",
            signal_id="SIG-001",
            correlation_id="CORR-001",
            approved=True,
            approved_quantity=100.0,
        )
    with pytest.raises(ValueError):
        RiskDecision(
            decision_id="RISK-001",
            intent_id="INT-001",
            strategy_id="STRAT-001",
            session_id="SESSION-001",
            signal_id="SIG-001",
            correlation_id="",
            approved=True,
            approved_quantity=100.0,
        )


def test_decision_as_dict() -> None:
    decision = approved_decision(decided_at=999.0)
    mapping = decision.as_dict()
    assert mapping["approved"] is True
    assert mapping["approved_quantity"] == 100.0
    assert mapping["intent_id"] == "INT-001"
    assert mapping["correlation_id"] == "CORR-001"


def test_new_decision_id_shape() -> None:
    decision_id = new_decision_id(1775000000.0)
    from datetime import datetime

    date_part = datetime.fromtimestamp(1775000000.0).strftime("%Y%m%d")
    assert decision_id.startswith(f"RISK-{date_part}-")


def test_approved_decision_factory_generates_ids() -> None:
    first = approved_decision(decided_at=1000.0)
    second = approved_decision(decided_at=1000.0)
    assert first.decision_id != second.decision_id
