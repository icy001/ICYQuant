import pytest

from services.order import (
    InvalidStateTransition,
    OrderStateMachine,
    OrderStatus,
)


def test_valid_transition():

    assert OrderStateMachine.transition(

        OrderStatus.NEW,

        OrderStatus.PENDING,

    ) == OrderStatus.PENDING


def test_invalid_transition():

    with pytest.raises(

        InvalidStateTransition

    ):

        OrderStateMachine.transition(

            OrderStatus.FILLED,

            OrderStatus.CANCELLED,

        )


def test_partial_to_filled():

    assert OrderStateMachine.transition(

        OrderStatus.PARTIALLY_FILLED,

        OrderStatus.FILLED,

    ) == OrderStatus.FILLED