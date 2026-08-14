"""Tests for the order engine domain services (Commit 33 Part 1.1)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime
from decimal import Decimal

import pytest

from services.order.domain.order import Order
from services.order.domain.order_side import OrderSide
from services.order.domain.order_state import (
    InvalidOrderStateTransition,
    OrderStateMachine,
)
from services.order.domain.order_status import OrderStatus
from services.order.domain.order_type import OrderType
from services.order.domain.time_in_force import TimeInForce
from services.order.engine.contract import CreateOrderCommand
from services.order.engine.model import (
    OrderCreationError,
    OrderFactory,
    OrderRepository,
)
from services.order.request.normalization import NormalizedOrderRequest
from services.order.request.repository import OrderRequestSnapshot
from services.order.request.state import OrderRequestState

TIMESTAMP = datetime(2026, 8, 13, 9, 30, 0)


def make_request(
    state: OrderRequestState = OrderRequestState.HANDOFF,
    **overrides,
) -> OrderRequestSnapshot:
    defaults = dict(
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
        side="BUY",
        quantity=100.0,
        order_type="MARKET",
        time_in_force="DAY",
        limit_price=None,
        idempotency_key="STRAT-001:SESSION-001:INT-001",
        created_at=1000.0,
        state=state,
    )
    defaults.update(overrides)
    return OrderRequestSnapshot(**defaults)


def make_handoff_request(**overrides) -> OrderRequestSnapshot:
    return make_request(state=OrderRequestState.HANDOFF, **overrides)


def make_command(
    request,
    client_order_id: str = "ICY-ORD-20260813-000001",
    timestamp: datetime = TIMESTAMP,
) -> CreateOrderCommand:
    return CreateOrderCommand(
        order_request_id=request.order_request_id,
        client_order_id=client_order_id,
        timestamp=timestamp,
    )


@pytest.fixture
def factory() -> OrderFactory:
    return OrderFactory()


@pytest.fixture
def state_machine() -> OrderStateMachine:
    return OrderStateMachine()


# --- Spec #31: order creation ---------------------------------------------


def test_create_order_from_handoff_request(factory):
    request = make_handoff_request()
    command = make_command(request)

    order = factory.create(request, command)

    assert isinstance(order, Order)
    assert order.status is OrderStatus.CREATED
    assert order.order_request_id == request.order_request_id
    assert order.order_id.startswith("ORD-")


# --- Spec #32: lineage preservation ---------------------------------------


def test_order_preserves_authorization_lineage(factory):
    request = make_handoff_request(
        intent_id="INT-001",
        authorization_id="AUTH-001",
        certificate_id="CERT-001",
        decision_id="DECISION-001",
        strategy_id="STRAT-001",
        session_id="SESSION-001",
        signal_id="SIG-001",
        correlation_id="CORR-001",
    )

    order = factory.create(request, make_command(request))

    assert order.intent_id == "INT-001"
    assert order.authorization_id == "AUTH-001"
    assert order.certificate_id == "CERT-001"
    assert order.decision_id == "DECISION-001"
    assert order.strategy_id == "STRAT-001"
    assert order.session_id == "SESSION-001"
    assert order.signal_id == "SIG-001"
    assert order.correlation_id == "CORR-001"


# --- Spec #33: request must be HANDOFF ------------------------------------


def test_order_requires_handoff_request(factory):
    request = make_request(state=OrderRequestState.NORMALIZED)

    with pytest.raises(OrderCreationError):
        factory.create(request, make_command(request))


@pytest.mark.parametrize(
    "state",
    [
        OrderRequestState.CREATED,
        OrderRequestState.VALIDATED,
        OrderRequestState.NORMALIZED,
        OrderRequestState.SUBMITTED,
        OrderRequestState.ACCEPTED,
    ],
)
def test_no_order_from_pre_handoff_states(factory, state):
    request = make_request(state=state)
    with pytest.raises(OrderCreationError):
        factory.create(request, make_command(request))


def test_plain_normalized_request_has_no_state_and_is_rejected(factory):
    # A raw NormalizedOrderRequest (no state attribute) is not a HANDOFF
    # request yet - the engine fails closed instead of guessing.
    normalized = NormalizedOrderRequest(
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
        side="BUY",
        quantity=100.0,
        order_type="MARKET",
        time_in_force="DAY",
        limit_price=None,
        idempotency_key="STRAT-001:SESSION-001:INT-001",
        created_at=1000.0,
    )
    with pytest.raises(OrderCreationError):
        factory.create(normalized, make_command(normalized))


# --- Spec #34: invalid state jump ------------------------------------------


def test_order_cannot_jump_to_filled(state_machine):
    with pytest.raises(InvalidOrderStateTransition):
        state_machine.transition(OrderStatus.CREATED, OrderStatus.FILLED)


def test_state_machine_requires_full_lifecycle(state_machine):
    assert not state_machine.can_transition(
        OrderStatus.CREATED, OrderStatus.ACCEPTED
    )
    assert state_machine.can_transition(
        OrderStatus.ACCEPTED, OrderStatus.FILLED
    )


# --- Spec #35: LIMIT requires price ----------------------------------------


def test_limit_order_requires_price(factory):
    request = make_handoff_request(order_type="LIMIT", limit_price=None)

    with pytest.raises(OrderCreationError):
        factory.create(request, make_command(request))


def test_limit_order_requires_positive_price(factory):
    request = make_handoff_request(order_type="LIMIT", limit_price=0.0)

    with pytest.raises(OrderCreationError):
        factory.create(request, make_command(request))


# --- Spec #36: MARKET has no price ------------------------------------------


def test_market_order_has_no_limit_price(factory):
    request = make_handoff_request(order_type="MARKET", limit_price=None)

    order = factory.create(request, make_command(request))

    assert order.limit_price is None


def test_market_order_rejects_price(factory):
    request = make_handoff_request(order_type="MARKET", limit_price=180.0)

    with pytest.raises(OrderCreationError):
        factory.create(request, make_command(request))


# --- Spec #37: Decimal quantities and prices --------------------------------


def test_factory_converts_to_exact_decimal(factory):
    request = make_handoff_request(
        order_type="LIMIT",
        quantity=100.25,
        limit_price=180.50,
    )

    order = factory.create(request, make_command(request))

    assert isinstance(order.quantity, Decimal)
    assert isinstance(order.limit_price, Decimal)
    assert order.quantity == Decimal("100.25")
    assert order.limit_price == Decimal("180.50")


def test_factory_decimal_conversion_is_not_binary_float(factory):
    request = make_handoff_request(
        order_type="LIMIT",
        quantity=0.1,
        limit_price=0.2,
    )

    order = factory.create(request, make_command(request))

    assert str(order.quantity) == "0.1"
    assert str(order.limit_price) == "0.2"
    # 0.1 + 0.2 as floats would be 0.30000000000000004; Decimals stay exact.
    assert order.quantity + order.limit_price == Decimal("0.3")


# --- Additional boundary tests ---------------------------------------------


def test_command_must_target_the_same_request(factory):
    request = make_handoff_request()
    other = make_handoff_request(order_request_id="OR-20260813-000002")
    command = make_command(other)

    with pytest.raises(OrderCreationError):
        factory.create(request, command)


def test_factory_rejects_negative_quantity(factory):
    request = make_handoff_request(quantity=-5.0)

    with pytest.raises(OrderCreationError):
        factory.create(request, make_command(request))


def test_factory_rejects_none_request(factory):
    with pytest.raises(OrderCreationError):
        factory.create(None, make_command(make_request()))  # type: ignore[arg-type]


def test_order_side_is_normalized_from_request(factory):
    request = make_handoff_request(side="SELL")

    order = factory.create(request, make_command(request))

    assert order.side is OrderSide.SELL


def test_order_metadata_is_copied_from_request(factory):
    request = make_handoff_request(symbol="NVDA", time_in_force="GTC")

    order = factory.create(request, make_command(request))

    assert order.symbol == "NVDA"
    assert order.time_in_force is TimeInForce.GTC
    assert order.order_type is OrderType.MARKET


def test_created_at_and_updated_at(factory):
    request = make_handoff_request(created_at=1000.0)
    command = make_command(request, timestamp=datetime(2026, 8, 13, 9, 30, 0))

    order = factory.create(request, command)

    assert order.created_at == datetime.fromtimestamp(1000.0)
    assert order.updated_at == datetime(2026, 8, 13, 9, 30, 0)


def test_create_order_command_is_frozen():
    command = make_command(make_request())
    with pytest.raises(FrozenInstanceError):
        command.order_request_id = "OR-999"  # type: ignore[misc]


def test_order_repository_protocol():
    class FakeRepository:
        def save(self, order: Order) -> None:
            pass

        def get(self, order_id: str) -> Order | None:
            return None

        def update(self, order: Order) -> None:
            pass

    assert isinstance(FakeRepository(), OrderRepository)


def test_order_repository_rejects_missing_methods():
    class Incomplete:
        def save(self, order: Order) -> None:
            pass

    assert not isinstance(Incomplete(), OrderRepository)
