"""Lifecycle-specific errors."""
from __future__ import annotations

from services.oms.domain.order_status import OrderStatus
from services.oms.domain.order_lifecycle import LifecycleEventType


class LifecycleError(Exception):
    """Base error for order lifecycle operations."""

    def __init__(self, message: str, order_id: str = "",
                 code: str = "") -> None:
        super().__init__(message)
        self.message: str = message
        self.order_id: str = order_id
        self.code: str = code or "LIFECYCLE_ERROR"


class InvalidStateTransitionError(LifecycleError):
    def __init__(self, order_id: str, from_status: OrderStatus,
                 to_status: OrderStatus, event_type: LifecycleEventType = LifecycleEventType.ORDER_RECEIVED) -> None:
        super().__init__(
            f"Invalid state transition for {order_id}: "
            f"{from_status.name} → {to_status.name} "
            f"(event={event_type.name})",
            order_id=order_id,
            code="INVALID_STATE_TRANSITION",
        )
        self.from_status = from_status
        self.to_status = to_status
        self.event_type = event_type


class TerminalStateModificationError(LifecycleError):
    def __init__(self, order_id: str, current: OrderStatus) -> None:
        super().__init__(
            f"Cannot modify order {order_id} in terminal state {current.name}",
            order_id=order_id,
            code="TERMINAL_STATE_MODIFICATION",
        )
        self.current_status = current


class UnknownExecutionStateError(LifecycleError):
    def __init__(self, order_id: str, execution_id: str = "") -> None:
        super().__init__(
            f"Unknown execution state for {order_id} (exec={execution_id})",
            order_id=order_id,
            code="EXECUTION_STATUS_UNKNOWN",
        )
        self.execution_id = execution_id


class ExecutionTimeoutError(LifecycleError):
    def __init__(self, order_id: str, gateway: str = "",
                 duration: float = 0.0) -> None:
        super().__init__(
            f"Execution gateway timeout for {order_id} "
            f"(gateway={gateway}, duration={duration:.1f}s)",
            order_id=order_id,
            code="EXECUTION_TIMEOUT",
        )
        self.gateway = gateway
        self.duration = duration
