"""Tests for the immutable OrderRequest domain model."""

from dataclasses import FrozenInstanceError
from typing import Optional

import pytest

from services.order.request.model import ORDER_TYPES, TIME_IN_FORCE_VALUES, OrderRequest


def make_order_request(**overrides) -> OrderRequest:
    defaults = dict(
        order_request_id="OR-20260813-000001",
        intent_id="INT-001",
        authorization_id="AUTH-001",
        certificate_id="CERT-001",
        decision_id="RISK-001",
        strategy_id="STRAT-001",
        session_id="SESSION-001",
        signal_id="SIG-001",
        correlation_id="CORR-001",
        symbol="NVDA",
        side="BUY",
        quantity=100.0,
        order_type="MARKET",
        time_in_force="DAY",
        limit_price=None,
        created_at=1000.0,
        idempotency_key="STRAT-001:SESSION-001:INT-001",
    )
    defaults.update(overrides)
    return OrderRequest(**defaults)


def test_order_request_is_frozen():
    request = make_order_request()
    with pytest.raises(FrozenInstanceError):
        request.quantity = 500.0
    with pytest.raises(FrozenInstanceError):
        request.side = "SELL"
    with pytest.raises(FrozenInstanceError):
        request.symbol = "AMD"


def test_order_request_fields():
    request = make_order_request()
    assert request.order_request_id == "OR-20260813-000001"
    assert request.quantity == 100.0
    assert request.limit_price is None


def test_order_request_as_dict():
    request = make_order_request()
    data = request.as_dict()
    assert data["order_request_id"] == "OR-20260813-000001"
    assert data["symbol"] == "NVDA"
    assert data["side"] == "BUY"
    assert data["quantity"] == 100.0
    assert data["idempotency_key"] == "STRAT-001:SESSION-001:INT-001"


def test_order_types_are_supported():
    assert ORDER_TYPES == {"MARKET", "LIMIT"}


def test_time_in_force_values_are_supported():
    assert TIME_IN_FORCE_VALUES == {"DAY", "GTC", "IOC", "FOK"}


def test_limit_price_optional():
    request = make_order_request(order_type="LIMIT", limit_price=180.0)
    assert request.limit_price == 180.0


def test_quantity_optional_type_is_float():
    request: OrderRequest = make_order_request(quantity=300.0)
    assert isinstance(request.quantity, float)


def test_limit_price_none_type():
    request: Optional[OrderRequest] = make_order_request()
    assert request.limit_price is None
