"""Execution errors."""
from __future__ import annotations


class ExecutionError(Exception):
    """Base error for execution gateway operations."""

    def __init__(self, message: str, order_id: str = "",
                 request_id: str = "", code: str = "") -> None:
        super().__init__(message)
        self.message: str = message
        self.order_id: str = order_id
        self.request_id: str = request_id
        self.code: str = code or "EXECUTION_ERROR"


class ExecutionTimeoutError(ExecutionError):
    def __init__(self, order_id: str, request_id: str = "",
                 timeout_type: str = "SUBMISSION") -> None:
        super().__init__(
            f"Execution {timeout_type} timeout for {order_id}",
            order_id=order_id, request_id=request_id,
            code="EXECUTION_TIMEOUT",
        )
        self.timeout_type = timeout_type


class ExecutionUnknownError(ExecutionError):
    def __init__(self, order_id: str, request_id: str = "",
                 reason: str = "") -> None:
        super().__init__(
            f"Unknown execution state for {order_id}: {reason}",
            order_id=order_id, request_id=request_id,
            code="UNKNOWN_EXECUTION_STATE",
        )


class RequestIdReuseConflictError(ExecutionError):
    def __init__(self, request_id: str, order_id: str = "") -> None:
        super().__init__(
            f"Request ID {request_id} reused with different payload",
            order_id=order_id, request_id=request_id,
            code="REQUEST_ID_REUSE_CONFLICT",
        )


class ExecutionQuantityExceededError(ExecutionError):
    def __init__(self, order_id: str, requested: float,
                 available: float) -> None:
        super().__init__(
            f"Execution quantity exceeded for {order_id}: "
            f"requested {requested}, available {available}",
            order_id=order_id,
            code="EXECUTION_QUANTITY_EXCEEDED",
        )
        self.requested = requested
        self.available = available


class GatewayUnavailableError(ExecutionError):
    def __init__(self, reason: str = "") -> None:
        super().__init__(
            f"Execution gateway unavailable: {reason}",
            code="GATEWAY_UNAVAILABLE",
        )
