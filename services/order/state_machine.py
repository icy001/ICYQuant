"""
Order state machine.
"""

from __future__ import annotations

from .enums import OrderStatus


_ALLOWED_TRANSITIONS = {

    OrderStatus.NEW: {

        OrderStatus.PENDING,

        OrderStatus.REJECTED,

        OrderStatus.CANCELLED,

    },

    OrderStatus.PENDING: {

        OrderStatus.PARTIALLY_FILLED,

        OrderStatus.FILLED,

        OrderStatus.CANCELLED,

        OrderStatus.REJECTED,

    },

    OrderStatus.PARTIALLY_FILLED: {

        OrderStatus.PARTIALLY_FILLED,

        OrderStatus.FILLED,

        OrderStatus.CANCELLED,

    },

    OrderStatus.FILLED: set(),

    OrderStatus.CANCELLED: set(),

    OrderStatus.REJECTED: set(),

}


class InvalidStateTransition(
    ValueError,
):
    """Invalid order status transition."""


class OrderStateMachine:

    @staticmethod
    def can_transition(
        current: OrderStatus,
        target: OrderStatus,
    ) -> bool:

        return target in _ALLOWED_TRANSITIONS.get(
            current,
            set(),
        )

    @staticmethod
    def transition(
        current: OrderStatus,
        target: OrderStatus,
    ) -> OrderStatus:

        if not OrderStateMachine.can_transition(
            current,
            target,
        ):
            raise InvalidStateTransition(
                f"{current} -> {target} is not allowed"
            )

        return target