"""Event store errors."""
from __future__ import annotations


class EventStoreError(Exception):
    """Base error for event store operations."""

    def __init__(self, message: str, order_id: str = "",
                 code: str = "") -> None:
        super().__init__(message)
        self.message: str = message
        self.order_id: str = order_id
        self.code: str = code or "EVENT_STORE_ERROR"


class EventStreamNotFoundError(EventStoreError):
    def __init__(self, order_id: str) -> None:
        super().__init__(
            f"Event stream not found: {order_id}",
            order_id=order_id,
            code="EVENT_STREAM_NOT_FOUND",
        )


class EventStreamClosedError(EventStoreError):
    def __init__(self, order_id: str) -> None:
        super().__init__(
            f"Event stream closed (terminal event): {order_id}",
            order_id=order_id,
            code="EVENT_STREAM_CLOSED",
        )


class SnapshotValidationError(EventStoreError):
    def __init__(self, order_id: str, reason: str = "") -> None:
        super().__init__(
            f"Snapshot validation failed for {order_id}: {reason}",
            order_id=order_id,
            code="SNAPSHOT_VALIDATION_ERROR",
        )
