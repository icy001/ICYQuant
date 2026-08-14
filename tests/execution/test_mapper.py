"""Order -> Execution boundary tests (Commit 38 Part 1.1).

The mapper is the single place where the OMS order vocabulary is translated
into the Execution vocabulary.
"""

from decimal import Decimal
from types import SimpleNamespace

from services.execution.application.mapper import (
    execution_request_from_order,
    order_side_to_execution_side,
    order_type_to_execution_type,
)
from services.execution.domain.request import (
    ExecutionOrderType,
    ExecutionRequestStatus,
    ExecutionSide,
)
from services.order.domain.order_side import OrderSide
from services.order.domain.order_type import OrderType


def test_order_side_maps_to_execution_side():

    assert (
        order_side_to_execution_side(OrderSide.BUY)
        == ExecutionSide.BUY
    )
    assert (
        order_side_to_execution_side(OrderSide.SELL)
        == ExecutionSide.SELL
    )


def test_order_type_maps_to_execution_type():

    assert (
        order_type_to_execution_type(OrderType.MARKET)
        == ExecutionOrderType.MARKET
    )
    assert (
        order_type_to_execution_type(OrderType.LIMIT)
        == ExecutionOrderType.LIMIT
    )


def test_execution_request_from_market_order():

    order = SimpleNamespace(
        order_id="order-001",
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("100"),
        limit_price=None,
        strategy_id="strat-001",
    )

    request = execution_request_from_order(order)

    assert request.order_id == "order-001"
    assert request.symbol == "AAPL"
    assert request.side == ExecutionSide.BUY
    assert request.order_type == ExecutionOrderType.MARKET
    assert request.quantity == 100.0
    assert request.price is None
    assert request.strategy_id == "strat-001"
    assert request.status == ExecutionRequestStatus.CREATED


def test_execution_request_from_limit_order_carries_price():

    order = SimpleNamespace(
        order_id="order-002",
        symbol="NVDA",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=Decimal("50.5"),
        limit_price=Decimal("128.75"),
        strategy_id=None,
    )

    request = execution_request_from_order(order)

    assert request.side == ExecutionSide.SELL
    assert request.order_type == ExecutionOrderType.LIMIT
    assert request.quantity == 50.5
    assert request.price == 128.75


def test_execution_request_from_order_is_validated():

    order = SimpleNamespace(
        order_id="order-003",
        symbol="TSLA",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0"),
        limit_price=None,
        strategy_id=None,
    )

    try:
        execution_request_from_order(order)
    except ValueError as exc:
        assert "quantity" in str(exc)
    else:
        raise AssertionError("expected ValueError for zero quantity")
