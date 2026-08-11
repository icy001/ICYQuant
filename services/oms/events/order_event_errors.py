"""Order event errors."""
from __future__ import annotations


class OrderEventError(Exception):
    """Base error for order event operations."""

    def __init__(self, message: str, order_id: str = "",
                 event_id: str = "", code: str = "") -> None:
        super().__init__(message)
        self.message: str = message
        self.order_id: str = order_id
        self.event_id: str = event_id
        self.code: str = code or "ORDER_EVENT_ERROR"


class EventSequenceGapError(OrderEventError):
    def __init__(self, order_id: str, expected: int, actual: int) -> None:
        super().__init__(
            f"Event sequence gap for {order_id}: "
            f"expected {expected}, got {actual}",
            order_id=order_id,
            code="ORDER_EVENT_GAP",
        )
        self.expected = expected
        self.actual = actual


class DuplicateEventError(OrderEventError):
    def __init__(self, order_id: str, event_id: str,
                 sequence: int, idempotent: bool = False) -> None:
        super().__init__(
            f"Duplicate event {event_id} for {order_id} at sequence {sequence}",
            order_id=order_id,
            event_id=event_id,
            code="IDEMPOTENT_REPLAY" if idempotent else "DUPLICATE_EVENT",
        )
        self.sequence = sequence
        self.idempotent = idempotent


class EventCollisionError(OrderEventError):
    def __init__(self, order_id: str, event_id: str,
                 sequence: int) -> None:
        super().__init__(
            f"Event ID collision for {order_id}: "
            f"event_id {event_id} at sequence {sequence} "
            f"has different payload",
            order_id=order_id,
            event_id=event_id,
            code="EVENT_ID_COLLISION",
        )
        self.sequence = sequence


class EventHashChainError(OrderEventError):
    def __init__(self, order_id: str, event_id: str,
                 expected_hash: str, actual_hash: str) -> None:
        super().__init__(
            f"Event hash chain broken for {order_id} at {event_id}: "
            f"expected {expected_hash[:16]}..., got {actual_hash[:16]}...",
            order_id=order_id,
            event_id=event_id,
            code="ORDER_EVENT_CHAIN_INVALID",
        )
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash


class EventConcurrencyConflictError(OrderEventError):
    def __init__(self, order_id: str, expected_sequence: int,
                 actual_sequence: int) -> None:
        super().__init__(
            f"Concurrency conflict for {order_id}: "
            f"expected sequence {expected_sequence}, "
            f"actual {actual_sequence}",
            order_id=order_id,
            code="EVENT_CONCURRENCY_CONFLICT",
        )
        self.expected_sequence = expected_sequence
        self.actual_sequence = actual_sequence


class EventValidationError(OrderEventError):
    def __init__(self, order_id: str, field: str,
                 message: str = "") -> None:
        super().__init__(
            f"Event validation error for {order_id}.{field}: {message}",
            order_id=order_id,
            code="EVENT_VALIDATION_ERROR",
        )
        self.field = field


class EventIntegrityFailureError(OrderEventError):
    def __init__(self, order_id: str, reason: str = "") -> None:
        super().__init__(
            f"Event integrity failure for {order_id}: {reason}",
            order_id=order_id,
            code="EVENT_INTEGRITY_FAILURE",
        )
