"""Tests for the execution request model (Commit 33 Part 1.3 #5).

An :class:`ExecutionRequest` is the minimal immutable information needed to
send an order to a venue.  It deliberately carries no lineage: the execution
layer may never re-decide the trading intent.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from decimal import Decimal

import pytest

from services.order.domain.order_side import OrderSide
from services.order.domain.order_type import OrderType
from services.order.domain.time_in_force import TimeInForce
from services.order.engine.execution.request import ExecutionRequest

TS = datetime(2026, 8, 13, 9, 30, 0)


def _make_request(**overrides) -> ExecutionRequest:
    defaults = dict(
        execution_request_id="EXREQ-20260813-000001",
        order_id="ORD-20260813-000001",
        client_order_id="ICY-ORD-20260813-000001",
        symbol="NVDA",
        side=OrderSide.BUY,
        quantity=Decimal("100"),
        order_type=OrderType.MARKET,
        time_in_force=TimeInForce.DAY,
        limit_price=None,
        correlation_id="CORR-001",
        causation_id=None,
        timestamp=TS,
    )
    defaults.update(overrides)
    return ExecutionRequest(**defaults)


def test_request_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        _make_request().order_id = "OTHER"


def test_request_keeps_decimal_precision():
    request = _make_request(quantity=Decimal("100.50"))
    assert request.quantity == Decimal("100.50")
    assert isinstance(request.quantity, Decimal)


def test_request_carries_execution_attempt_identity():
    # Every attempt has its own id; the chain stays traceable via causation.
    request = _make_request(causation_id="EXREQ-20260813-000000")
    assert request.execution_request_id == "EXREQ-20260813-000001"
    assert request.causation_id == "EXREQ-20260813-000000"


def test_request_carries_no_lineage():
    # Spec #5: the execution layer never re-decides the trading intent.
    request = _make_request()
    for lineage_field in (
        "intent_id",
        "authorization_id",
        "certificate_id",
        "decision_id",
        "strategy_id",
        "session_id",
        "signal_id",
    ):
        assert not hasattr(request, lineage_field)
