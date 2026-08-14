"""Tests for the Order aggregate (Commit 33 Part 1.1)."""

from dataclasses import FrozenInstanceError
from datetime import datetime
from decimal import Decimal

import pytest

from services.order.domain.order import Order
from services.order.domain.order_side import OrderSide
from services.order.domain.order_status import OrderStatus
from services.order.domain.order_type import OrderType
from services.order.domain.time_in_force import TimeInForce


def make_order(**overrides) -> Order:
    defaults = dict(
        order_id="ORD-20260813-000001",
        order_request_id="OR-20260813-000001",
        intent_id="INT-001",
        authorization_id="AUTH-001",
        certificate_id="CERT-001",
        decision_id="DECISION-001",
        strategy_id="STRAT-001",
        session_id="SESSION-001",
        signal_id="SIG-001",
        correlation_id="CORR-001",
        symbol="NVDA",
        side=OrderSide.BUY,
        quantity=Decimal("100"),
        order_type=OrderType.LIMIT,
        time_in_force=TimeInForce.DAY,
        limit_price=Decimal("180.00"),
        status=OrderStatus.CREATED,
        created_at=datetime(2026, 8, 13, 9, 30, 0),
        updated_at=datetime(2026, 8, 13, 9, 30, 0),
    )
    defaults.update(overrides)
    return Order(**defaults)


def test_order_aggregate_fields():
    order = make_order()
    assert order.order_id == "ORD-20260813-000001"
    assert order.order_request_id == "OR-20260813-000001"
    assert order.symbol == "NVDA"
    assert order.side is OrderSide.BUY
    assert order.status is OrderStatus.CREATED


def test_order_uses_decimal():
    # Spec #37: quantity and price are exact Decimals, never binary floats.
    order = make_order(
        quantity=Decimal("100.25"),
        limit_price=Decimal("180.50"),
    )
    assert isinstance(order.quantity, Decimal)
    assert isinstance(order.limit_price, Decimal)
    assert order.quantity == Decimal("100.25")
    assert order.limit_price == Decimal("180.50")


def test_order_is_frozen():
    order = make_order()
    with pytest.raises(FrozenInstanceError):
        order.symbol = "AMD"  # type: ignore[misc]


def test_order_lineage_cannot_be_overwritten():
    order = make_order(
        intent_id="INT-001",
        authorization_id="AUTH-001",
        certificate_id="CERT-001",
        decision_id="DECISION-001",
    )
    updated = order.with_status(OrderStatus.PENDING_SUBMIT)
    # Status moved, lineage untouched (Spec #22 / #4).
    assert updated.status is OrderStatus.PENDING_SUBMIT
    assert updated.intent_id == "INT-001"
    assert updated.authorization_id == "AUTH-001"
    assert updated.certificate_id == "CERT-001"
    assert updated.decision_id == "DECISION-001"
    assert updated.strategy_id == order.strategy_id
    assert updated.signal_id == order.signal_id


def test_with_status_returns_new_instance():
    order = make_order()
    updated = order.with_status(OrderStatus.PENDING_SUBMIT)
    assert updated is not order
    assert order.status is OrderStatus.CREATED  # original unchanged


def test_with_status_refreshes_updated_at():
    order = make_order(updated_at=datetime(2026, 8, 13, 9, 30, 0))
    later = datetime(2026, 8, 13, 9, 31, 0)
    updated = order.with_status(OrderStatus.PENDING_SUBMIT, at=later)
    assert updated.updated_at == later


def test_market_order_limit_price_is_none():
    order = make_order(order_type=OrderType.MARKET, limit_price=None)
    assert order.limit_price is None


def test_as_dict_serializes_domain_values():
    data = make_order().as_dict()
    assert data["side"] == "BUY"
    assert data["quantity"] == "100"
    assert data["limit_price"] == "180.00"
    assert data["order_type"] == "LIMIT"
    assert data["status"] == "CREATED"
    assert data["created_at"] == "2026-08-13T09:30:00"
