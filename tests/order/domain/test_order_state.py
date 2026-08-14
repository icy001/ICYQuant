"""Tests for the OrderStateMachine (Commit 33 Part 1.1)."""

import pytest

from services.order.domain.order_state import (
    InvalidOrderStateTransition,
    OrderStateMachine,
)
from services.order.domain.order_status import OrderStatus


@pytest.fixture
def machine() -> OrderStateMachine:
    return OrderStateMachine()


def test_can_transition_created_to_pending_submit(machine):
    assert machine.can_transition(
        OrderStatus.CREATED, OrderStatus.PENDING_SUBMIT
    )


def test_transition_returns_target_status(machine):
    target = machine.transition(OrderStatus.CREATED, OrderStatus.PENDING_SUBMIT)
    assert target is OrderStatus.PENDING_SUBMIT


def test_order_cannot_jump_to_filled(machine):
    # Spec #34: CREATED -> FILLED is never allowed.
    with pytest.raises(InvalidOrderStateTransition):
        machine.transition(OrderStatus.CREATED, OrderStatus.FILLED)


def test_order_cannot_jump_to_accepted(machine):
    with pytest.raises(InvalidOrderStateTransition):
        machine.transition(OrderStatus.CREATED, OrderStatus.ACCEPTED)


def test_full_lifecycle_is_legal(machine):
    current = OrderStatus.CREATED
    for target in (
        OrderStatus.PENDING_SUBMIT,
        OrderStatus.SUBMITTED,
        OrderStatus.ACCEPTED,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
    ):
        assert machine.can_transition(current, target)
        current = target


def test_partial_fill_can_repeat(machine):
    # Spec #21: successive fills keep the order PARTIALLY_FILLED.
    assert machine.can_transition(
        OrderStatus.PARTIALLY_FILLED, OrderStatus.PARTIALLY_FILLED
    )
    assert machine.can_transition(OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED)


def test_cancel_path(machine):
    assert machine.can_transition(
        OrderStatus.ACCEPTED, OrderStatus.CANCEL_PENDING
    )
    assert machine.can_transition(
        OrderStatus.PARTIALLY_FILLED, OrderStatus.CANCEL_PENDING
    )
    assert machine.can_transition(
        OrderStatus.CANCEL_PENDING, OrderStatus.CANCELLED
    )
    assert not machine.can_transition(
        OrderStatus.ACCEPTED, OrderStatus.CANCELLED
    )


def test_reject_path(machine):
    assert machine.can_transition(OrderStatus.PENDING_SUBMIT, OrderStatus.REJECTED)
    assert machine.can_transition(OrderStatus.SUBMITTED, OrderStatus.REJECTED)
    assert not machine.can_transition(OrderStatus.ACCEPTED, OrderStatus.REJECTED)


def test_expire_path(machine):
    assert machine.can_transition(OrderStatus.ACCEPTED, OrderStatus.EXPIRED)
    assert not machine.can_transition(OrderStatus.SUBMITTED, OrderStatus.EXPIRED)


def test_terminal_states_have_no_transitions(machine):
    terminal = {
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
        OrderStatus.EXPIRED,
    }
    for current in terminal:
        for target in OrderStatus:
            assert not machine.can_transition(current, target)


def test_unknown_transition_raises(machine):
    with pytest.raises(InvalidOrderStateTransition):
        machine.transition(OrderStatus.PENDING_SUBMIT, OrderStatus.FILLED)
