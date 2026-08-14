"""Tests for the execution lineage."""

from datetime import datetime

import pytest

from services.strategy.execution.intent import ExecutionIntent
from services.strategy.execution.lineage import (
    ExecutionLineage,
    lineage_from_intent,
    new_correlation_id,
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


def test_new_correlation_id_shape() -> None:
    correlation_id = new_correlation_id(1775000000.0)
    date_part = datetime.fromtimestamp(1775000000.0).strftime("%Y%m%d")
    assert correlation_id.startswith("CORR-%s-" % date_part)
    assert correlation_id != new_correlation_id(1775000000.0)


def test_lineage_from_intent() -> None:
    lineage = lineage_from_intent(
        make_intent(),
        correlation_id="CORR-20260813-000001",
    )
    assert lineage.strategy_id == "STRAT-001"
    assert lineage.session_id == "SESSION-STRAT001-20260813-01"
    assert lineage.signal_id == "SIG-001"
    assert lineage.intent_id == "INTENT-20260813-000001"
    assert lineage.correlation_id == "CORR-20260813-000001"


def test_lineage_generates_correlation_id() -> None:
    lineage = lineage_from_intent(make_intent())
    assert lineage.correlation_id.startswith("CORR-")


def test_lineage_links_decision_order_fill() -> None:
    lineage = lineage_from_intent(
        make_intent(),
        correlation_id="CORR-20260813-000001",
    )
    lineage.link_decision("RISK-20260813-000001")
    lineage.link_order_request("OR-1")
    lineage.link_order("ORD-1")
    lineage.link_fill("FILL-1")
    assert lineage.decision_id == "RISK-20260813-000001"
    assert lineage.order_request_id == "OR-1"
    assert lineage.order_id == "ORD-1"
    assert lineage.fill_id == "FILL-1"


def test_lineage_link_methods_chain() -> None:
    lineage = lineage_from_intent(make_intent(), correlation_id="CORR-1")
    returned = lineage.link_decision("RISK-1").link_order_request("OR-1")
    assert returned is lineage
    assert lineage.decision_id == "RISK-1"
    assert lineage.order_request_id == "OR-1"


def test_lineage_rejects_empty_ids() -> None:
    lineage = ExecutionLineage(
        strategy_id="STRAT-001",
        session_id="SESSION-1",
        signal_id="SIG-1",
        intent_id="INTENT-1",
        correlation_id="CORR-1",
    )
    with pytest.raises(ValueError):
        lineage.link_decision("")
    with pytest.raises(ValueError):
        lineage.link_order_request("")
    with pytest.raises(ValueError):
        lineage.link_order("")
    with pytest.raises(ValueError):
        lineage.link_fill("")


def test_lineage_as_dict() -> None:
    lineage = lineage_from_intent(
        make_intent(),
        correlation_id="CORR-20260813-000001",
    )
    lineage.link_decision("RISK-20260813-000001")
    data = lineage.as_dict()
    assert data["strategy_id"] == "STRAT-001"
    assert data["intent_id"] == "INTENT-20260813-000001"
    assert data["correlation_id"] == "CORR-20260813-000001"
    assert data["decision_id"] == "RISK-20260813-000001"
    assert data["order_request_id"] is None
    assert data["order_id"] is None
    assert data["fill_id"] is None
