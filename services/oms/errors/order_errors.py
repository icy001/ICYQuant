"""Order-level errors for the OMS domain."""
from __future__ import annotations

from typing import Optional

from services.oms.domain.order_status import OrderStatus


class OrderError(Exception):
    """Base error for OMS order operations."""

    def __init__(self, message: str, order_id: str = "",
                 code: str = "") -> None:
        super().__init__(message)
        self.message: str = message
        self.order_id: str = order_id
        self.code: str = code or "ORDER_ERROR"


class OrderNotFoundError(OrderError):
    def __init__(self, order_id: str) -> None:
        super().__init__(
            f"Order not found: {order_id}",
            order_id=order_id,
            code="ORDER_NOT_FOUND",
        )


class OrderNotAcceptedError(OrderError):
    def __init__(self, order_id: str, reason: str = "") -> None:
        msg = f"Order not accepted: {order_id}"
        if reason:
            msg += f" — {reason}"
        super().__init__(msg, order_id=order_id, code="ORDER_NOT_ACCEPTED")
        self.reason = reason


class OrderCertificateError(OrderError):
    def __init__(self, order_id: str = "", certificate_id: str = "",
                 reason: str = "") -> None:
        super().__init__(
            f"Invalid certificate for order {order_id}: {reason}",
            order_id=order_id,
            code="ORDER_CERTIFICATE_INVALID",
        )
        self.certificate_id = certificate_id


class OrderLineageError(OrderError):
    def __init__(self, order_id: str = "", lineage_id: str = "",
                 reason: str = "") -> None:
        super().__init__(
            f"Lineage error for order {order_id}: {reason}",
            order_id=order_id,
            code="ORDER_LINEAGE_ERROR",
        )
        self.lineage_id = lineage_id


class OrderIdempotencyError(OrderError):
    def __init__(self, client_order_id: str,
                 existing_order_id: str = "") -> None:
        super().__init__(
            f"Duplicate client_order_id: {client_order_id}",
            order_id=existing_order_id,
            code="DUPLICATE_CLIENT_ORDER_ID",
        )
        self.client_order_id = client_order_id


class OrderQuantityInconsistencyError(OrderError):
    def __init__(self, order_id: str, filled: float = 0,
                 remaining: float = 0, cancelled: float = 0,
                 original: float = 0) -> None:
        super().__init__(
            f"Quantity inconsistency for {order_id}: "
            f"filled={filled} remaining={remaining} cancelled={cancelled} "
            f"!= original={original}",
            order_id=order_id,
            code="ORDER_QUANTITY_INCONSISTENCY",
        )
        self.filled = filled
        self.remaining = remaining
        self.cancelled = cancelled
        self.original = original


class ParentQuantityExceededError(OrderError):
    def __init__(self, parent_order_id: str, parent_qty: float,
                 child_total: float) -> None:
        super().__init__(
            f"Parent order {parent_order_id} quantity {parent_qty} "
            f"exceeded by children: {child_total}",
            order_id=parent_order_id,
            code="PARENT_QUANTITY_EXCEEDED",
        )
        self.parent_qty = parent_qty
        self.child_total = child_total


class ConcurrentModificationError(OrderError):
    def __init__(self, order_id: str, expected_version: int,
                 actual_version: int) -> None:
        super().__init__(
            f"Concurrent modification of {order_id}: "
            f"expected version {expected_version}, got {actual_version}",
            order_id=order_id,
            code="CONCURRENT_MODIFICATION",
        )
        self.expected_version = expected_version
        self.actual_version = actual_version


class OrderValidationError(OrderError):
    def __init__(self, order_id: str, field: str,
                 message: str = "") -> None:
        super().__init__(
            f"Validation error on {order_id}.{field}: {message}",
            order_id=order_id,
            code="ORDER_VALIDATION_ERROR",
        )
        self.field = field
