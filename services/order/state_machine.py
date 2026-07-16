"""
Order state machine.
"""

from __future__ import annotations

from .enums import OrderStatus
from .events import OrderTransition
from .transition import TRANSITIONS


class InvalidStateTransition(ValueError):
    """Invalid order status transition."""


class OrderStateMachine:
    @staticmethod
    def apply(current: OrderStatus, event: OrderTransition) -> OrderStatus:
        key = (current, event)
        if key not in TRANSITIONS:
            raise InvalidStateTransition(f"{current} + {event}")
        return TRANSITIONS[key]

    @staticmethod
    def can_transition(current: OrderStatus, target: OrderStatus) -> bool:
        for (src, _), dest in TRANSITIONS.items():
            if src == current and dest == target:
                return True
        return False

    @staticmethod
    def transition(current: OrderStatus, target: OrderStatus) -> OrderStatus:
        if not OrderStateMachine.can_transition(current, target):
            raise InvalidStateTransition(f"{current} -> {target} is not allowed")
        return target