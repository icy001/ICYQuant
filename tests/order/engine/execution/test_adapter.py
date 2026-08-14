"""Tests for the execution adapter (Commit 33 Part 1.3 #12/#20).

The adapter is the mechanical bridge Order -> ExecutionRequest -> Gateway.  It
performs NO trading decisions and never copies the authorization lineage.
"""

from __future__ import annotations

from decimal import Decimal

from services.order.domain.order_side import OrderSide
from services.order.domain.order_type import OrderType
from services.order.domain.time_in_force import TimeInForce
from services.order.engine.execution.request import ExecutionRequest
from services.order.engine.execution.response import ExecutionResponseStatus


def test_build_request_copies_trading_parameters(adapter, make_order):
    order = make_order(
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=Decimal("250"),
        order_type=OrderType.LIMIT,
        time_in_force=TimeInForce.GTC,
        limit_price=Decimal("212.50"),
    )
    request = adapter.build_request(order)

    assert isinstance(request, ExecutionRequest)
    assert request.symbol == "AAPL"
    assert request.side is OrderSide.SELL
    assert request.quantity == Decimal("250")
    assert request.order_type is OrderType.LIMIT
    assert request.time_in_force is TimeInForce.GTC
    assert request.limit_price == Decimal("212.50")


def test_build_request_copies_identity(adapter, make_order):
    order = make_order()
    request = adapter.build_request(order)

    assert request.order_id == order.order_id
    assert request.client_order_id == order.client_order_id
    assert request.correlation_id == order.correlation_id


def test_build_request_generates_execution_request_id(adapter, make_order):
    request = adapter.build_request(make_order())
    assert request.execution_request_id.startswith("EXREQ-")


def test_build_request_accepts_explicit_execution_request_id(adapter, make_order):
    request = adapter.build_request(
        make_order(),
        execution_request_id="EXREQ-20260813-000042",
    )
    assert request.execution_request_id == "EXREQ-20260813-000042"


def test_build_request_chains_causation_id(adapter, make_order):
    # Spec #20: a retry keeps the previous execution request as its causation.
    previous = adapter.build_request(make_order())
    retry = adapter.build_request(
        make_order(),
        execution_request_id="EXREQ-20260813-000002",
        causation_id=previous.execution_request_id,
    )
    assert retry.causation_id == previous.execution_request_id


def test_build_request_never_copies_lineage(adapter, make_order):
    order = make_order(intent_id="INT-001")
    request = adapter.build_request(order)
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


def test_build_request_client_order_id_falls_back_to_order_id(adapter, make_order):
    order = make_order(client_order_id=None)
    request = adapter.build_request(order)
    assert request.client_order_id == order.order_id


def test_build_request_timestamp_defaults_to_updated_at(adapter, make_order):
    order = make_order()
    request = adapter.build_request(order)
    assert request.timestamp == order.updated_at


def test_submit_goes_through_the_gateway(adapter, make_order):
    response = adapter.submit(make_order())
    assert response.status is ExecutionResponseStatus.ACCEPTED


def test_cancel_goes_through_the_gateway(adapter, make_order):
    response = adapter.cancel(make_order())
    assert response.status is ExecutionResponseStatus.ACCEPTED


def test_query_delegates_to_the_gateway(adapter, gateway, make_order):
    order = make_order()
    adapter.submit(order)
    response = adapter.query(order.order_id)
    assert response is not None
    assert response.order_id == order.order_id
    assert gateway.query(order.order_id) is response
