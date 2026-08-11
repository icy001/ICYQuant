"""LifecycleValidator — validates state transitions for commands."""
from __future__ import annotations

from services.oms.domain.order_status import OrderStatus
from services.oms.domain.order_lifecycle import LifecycleEventType
from services.oms.application.order_state_machine import OrderStateMachine
from services.oms.results.command_errors import (
    InvalidStateTransitionError,
    TerminalStateError,
)


class LifecycleValidator:
    """Validates that a command's state transition is legal.

    Uses the OrderStateMachine to check:
      - Current status allows the transition
      - Terminal states are protected
    """

    # Maps command type → event type for transition checking
    _COMMAND_EVENT_MAP = {
        "START_ROUTING": LifecycleEventType.ORDER_ROUTING_STARTED,
        "MARK_WORKING": LifecycleEventType.ORDER_WORKING,
        "APPLY_EXECUTION": LifecycleEventType.ORDER_PARTIAL_FILL,  # or FILLED
        "REQUEST_CANCEL": LifecycleEventType.ORDER_CANCEL_REQUESTED,
        "CONFIRM_CANCEL": LifecycleEventType.ORDER_CANCEL_CONFIRMED,
        "REJECT_ORDER": LifecycleEventType.ORDER_REJECTED,
        "EXPIRE_ORDER": LifecycleEventType.ORDER_EXPIRED,
    }

    @staticmethod
    def validate_transition(command_type: str,
                            current_status: OrderStatus,
                            order_id: str = "",
                            command_id: str = "") -> None:
        """Validate that the command can be applied from current_status.

        Raises:
            TerminalStateError: if current_status is terminal.
            InvalidStateTransitionError: if the transition is not allowed.
        """
        if current_status.is_terminal:
            raise TerminalStateError(
                command_id, order_id, current_status.name,
            )

        event_type = LifecycleValidator._COMMAND_EVENT_MAP.get(command_type)
        if event_type is None:
            return  # No transition check for this command type

        if not OrderStateMachine.can_transition(current_status, event_type):
            raise InvalidStateTransitionError(
                command_id, order_id,
                current_status.name, command_type,
            )

    @staticmethod
    def can_apply_execution(current_status: OrderStatus) -> bool:
        """Check if an execution fill can be applied."""
        if current_status.is_terminal:
            return False
        return current_status in (OrderStatus.WORKING, OrderStatus.PARTIALLY_FILLED)

    @staticmethod
    def can_cancel(current_status: OrderStatus) -> bool:
        """Check if a cancel can be requested."""
        if current_status.is_terminal:
            return False
        return current_status in (
            OrderStatus.CREATED, OrderStatus.ROUTING,
            OrderStatus.WORKING, OrderStatus.PARTIALLY_FILLED,
        )

    @staticmethod
    def can_reject(current_status: OrderStatus) -> bool:
        """Check if a reject can be applied."""
        if current_status.is_terminal:
            return False
        return current_status in (
            OrderStatus.RECEIVED, OrderStatus.CREATED,
            OrderStatus.ROUTING, OrderStatus.WORKING,
        )

    @staticmethod
    def can_expire(current_status: OrderStatus) -> bool:
        """Check if an expire can be applied."""
        if current_status.is_terminal:
            return False
        return current_status in (
            OrderStatus.WORKING, OrderStatus.PARTIALLY_FILLED,
        )
