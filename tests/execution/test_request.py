import pytest

from services.execution.domain.request import (
    ExecutionOrderType,
    ExecutionRequest,
    ExecutionRequestStatus,
    ExecutionSide,
)


def test_execution_request_creation():

    request = ExecutionRequest(
        request_id="exec-001",
        order_id="order-001",
        symbol="AAPL",
        side=ExecutionSide.BUY,
        order_type=ExecutionOrderType.MARKET,
        quantity=100,
    )

    request.validate()

    assert request.request_id == "exec-001"
    assert request.order_id == "order-001"
    assert request.symbol == "AAPL"
    assert request.quantity == 100
    assert request.status == ExecutionRequestStatus.CREATED


def test_execution_request_requires_positive_quantity():

    request = ExecutionRequest(
        request_id="exec-001",
        order_id="order-001",
        symbol="AAPL",
        side=ExecutionSide.BUY,
        order_type=ExecutionOrderType.MARKET,
        quantity=0,
    )

    with pytest.raises(ValueError):
        request.validate()


def test_limit_order_requires_price():

    request = ExecutionRequest(
        request_id="exec-001",
        order_id="order-001",
        symbol="AAPL",
        side=ExecutionSide.BUY,
        order_type=ExecutionOrderType.LIMIT,
        quantity=100,
    )

    with pytest.raises(ValueError):
        request.validate()


def test_stop_order_requires_stop_price():

    request = ExecutionRequest(
        request_id="exec-001",
        order_id="order-001",
        symbol="AAPL",
        side=ExecutionSide.BUY,
        order_type=ExecutionOrderType.STOP,
        quantity=100,
    )

    with pytest.raises(ValueError):
        request.validate()


def test_stop_limit_order_requires_price_and_stop_price():

    request = ExecutionRequest(
        request_id="exec-001",
        order_id="order-001",
        symbol="AAPL",
        side=ExecutionSide.SELL,
        order_type=ExecutionOrderType.STOP_LIMIT,
        quantity=100,
        stop_price=95,
    )

    with pytest.raises(ValueError):
        request.validate()


def test_request_id_is_required():

    request = ExecutionRequest(
        request_id="",
        order_id="order-001",
        symbol="AAPL",
        side=ExecutionSide.BUY,
        order_type=ExecutionOrderType.MARKET,
        quantity=100,
    )

    with pytest.raises(ValueError):
        request.validate()


def test_execution_request_is_immutable():

    request = ExecutionRequest(
        request_id="exec-001",
        order_id="order-001",
        symbol="AAPL",
        side=ExecutionSide.BUY,
        order_type=ExecutionOrderType.MARKET,
        quantity=100,
    )

    with pytest.raises(Exception):
        request.quantity = 200
