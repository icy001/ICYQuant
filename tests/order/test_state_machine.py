import pytest

from services.order import (
    InvalidStateTransition,
    OrderStateMachine,
    OrderStatus,
)
from services.order.events import OrderTransition


def test_valid_apply_transition():
    assert OrderStateMachine.apply(
        OrderStatus.NEW, OrderTransition.SUBMIT
    ) == OrderStatus.PENDING


def test_invalid_apply_transition():
    with pytest.raises(InvalidStateTransition):
        OrderStateMachine.apply(
            OrderStatus.FILLED, OrderTransition.FILL
        )


def test_partial_to_filled_apply():
    assert OrderStateMachine.apply(
        OrderStatus.PARTIALLY_FILLED, OrderTransition.FILL
    ) == OrderStatus.FILLED


def test_can_transition():
    assert OrderStateMachine.can_transition(
        OrderStatus.NEW, OrderStatus.PENDING
    )
    assert not OrderStateMachine.can_transition(
        OrderStatus.FILLED, OrderStatus.CANCELLED
    )


def test_transition_backward_compat():
    assert OrderStateMachine.transition(
        OrderStatus.NEW, OrderStatus.PENDING
    ) == OrderStatus.PENDING

    with pytest.raises(InvalidStateTransition):
        OrderStateMachine.transition(
            OrderStatus.FILLED, OrderStatus.CANCELLED
        )