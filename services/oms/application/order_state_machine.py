"""OrderStateMachine — strict finite state machine for order transitions.

All order state transitions MUST go through this state machine.
Direct assignment `order.status = FILLED` is prohibited.

The state machine validates:
    current_state + event → next_state

and rejects any transition not in the allowed table. Terminal states
(FILLED, CANCELLED, REJECTED, EXPIRED, FAILED) cannot transition back
to active states.
"""
from __future__ import annotations

from typing import Dict, FrozenSet, Tuple

from services.oms.domain.order_status import OrderStatus
from services.oms.domain.order_lifecycle import (
    LifecycleEventType,
    _EVENT_TRANSITIONS,
)
from services.oms.errors.lifecycle_errors import (
    InvalidStateTransitionError,
    TerminalStateModificationError,
)


# ── Allowed transitions table ──────────────────────────
# (from_status, event_type) → to_status
# Built from _EVENT_TRANSITIONS in order_lifecycle.py for a single
# source of truth, but kept here as a fast lookup table.

_TRANSITIONS: Dict[Tuple[OrderStatus, LifecycleEventType], OrderStatus] = {}
for _evt, (_from_statuses, _to_status) in _EVENT_TRANSITIONS.items():
    if not _from_statuses:
        # Initial event — valid from "None" state (RECEIVED)
        _TRANSITIONS[(OrderStatus.RECEIVED, _evt)] = OrderStatus.RECEIVED
    else:
        for _from in _from_statuses:
            _TRANSITIONS[(_from, _evt)] = _to_status


_TERMINAL: FrozenSet[OrderStatus] = frozenset({
    OrderStatus.FILLED,
    OrderStatus.CANCELLED,
    OrderStatus.REJECTED,
    OrderStatus.EXPIRED,
    OrderStatus.FAILED,
})


class OrderStateMachine:
    """Validates and executes order state transitions.

    Usage:
        sm = OrderStateMachine()
        new_status = sm.transition(order.status,
                                   LifecycleEventType.ORDER_ACCEPTED)
        order.status = new_status

    The state machine is stateless — all state lives on the Order.
    """

    # ── Query ──────────────────────────────────────

    @staticmethod
    def can_transition(from_status: OrderStatus,
                       event_type: LifecycleEventType) -> bool:
        """Whether the transition is allowed."""
        if from_status in _TERMINAL:
            return False
        return (from_status, event_type) in _TRANSITIONS

    @staticmethod
    def next_status(from_status: OrderStatus,
                    event_type: LifecycleEventType) -> OrderStatus:
        """Return the target status without performing the transition."""
        if from_status in _TERMINAL:
            raise TerminalStateModificationError("", from_status)
        key = (from_status, event_type)
        if key not in _TRANSITIONS:
            raise InvalidStateTransitionError(
                "",
                from_status,
                from_status,  # unknown target
                event_type,
            )
        return _TRANSITIONS[key]

    @staticmethod
    def is_terminal(status: OrderStatus) -> bool:
        return status in _TERMINAL

    @staticmethod
    def is_valid_event_sequence(events: list) -> bool:
        """Check that an event sequence is internally consistent.

        `events` is a list of LifecycleEventType values.
        """
        if not events:
            return True
        # Initial event must be ORDER_RECEIVED
        if events[0] != LifecycleEventType.ORDER_RECEIVED:
            return False
        current = OrderStatus.RECEIVED
        for evt in events[1:]:
            try:
                current = OrderStateMachine.next_status(current, evt)
            except (InvalidStateTransitionError,
                    TerminalStateModificationError):
                return False
        return True

    # ── Execute ────────────────────────────────────

    @staticmethod
    def transition(from_status: OrderStatus,
                   event_type: LifecycleEventType,
                   order_id: str = "") -> OrderStatus:
        """Validate and return the next status.

        Raises:
            TerminalStateModificationError: if from_status is terminal.
            InvalidStateTransitionError: if the transition is not allowed.
        """
        if from_status in _TERMINAL:
            raise TerminalStateModificationError(order_id, from_status)
        key = (from_status, event_type)
        if key not in _TRANSITIONS:
            raise InvalidStateTransitionError(
                order_id, from_status, from_status, event_type,
            )
        return _TRANSITIONS[key]

    @staticmethod
    def allowed_events(from_status: OrderStatus) -> list:
        """Return the list of event types valid from this status."""
        if from_status in _TERMINAL:
            return []
        return [evt for (s, evt) in _TRANSITIONS if s == from_status]
