from services.order.enums import OrderStatus
from services.order.events import OrderTransition
from services.order.state_machine import (
    InvalidStateTransition,
    OrderStateMachine,
)


def test_submit():
    assert OrderStateMachine.apply(
        OrderStatus.NEW, OrderTransition.SUBMIT
    ) == OrderStatus.PENDING


def test_partial_fill_from_pending():
    assert OrderStateMachine.apply(
        OrderStatus.PENDING, OrderTransition.PARTIAL_FILL
    ) == OrderStatus.PARTIALLY_FILLED


def test_fill_from_pending():
    assert OrderStateMachine.apply(
        OrderStatus.PENDING, OrderTransition.FILL
    ) == OrderStatus.FILLED


def test_cancel_from_pending():
    assert OrderStateMachine.apply(
        OrderStatus.PENDING, OrderTransition.CANCEL
    ) == OrderStatus.CANCELLED


def test_reject_from_pending():
    assert OrderStateMachine.apply(
        OrderStatus.PENDING, OrderTransition.REJECT
    ) == OrderStatus.REJECTED


def test_partial_fill_from_partially_filled():
    assert OrderStateMachine.apply(
        OrderStatus.PARTIALLY_FILLED, OrderTransition.PARTIAL_FILL
    ) == OrderStatus.PARTIALLY_FILLED


def test_fill_from_partially_filled():
    assert OrderStateMachine.apply(
        OrderStatus.PARTIALLY_FILLED, OrderTransition.FILL
    ) == OrderStatus.FILLED


def test_cancel_from_partially_filled():
    assert OrderStateMachine.apply(
        OrderStatus.PARTIALLY_FILLED, OrderTransition.CANCEL
    ) == OrderStatus.CANCELLED


def test_illegal_transition():
    try:
        OrderStateMachine.apply(
            OrderStatus.FILLED, OrderTransition.FILL
        )
        assert False
    except InvalidStateTransition:
        pass