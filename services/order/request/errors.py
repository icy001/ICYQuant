"""Order request validation error model.

The validator collects every domain problem in one pass and exposes them as
stable, machine-readable :class:`OrderRequestErrorCode` values, so the caller
sees all issues at once instead of fixing one error at a time.
"""

from __future__ import annotations

from enum import Enum
from typing import Iterable, Optional, Tuple


class OrderRequestErrorCode(str, Enum):
    """Stable error codes raised by order request validation / normalization."""

    INVALID_REQUEST = "INVALID_REQUEST"
    MISSING_LINEAGE = "MISSING_LINEAGE"
    INVALID_SYMBOL = "INVALID_SYMBOL"
    INVALID_SIDE = "INVALID_SIDE"
    INVALID_QUANTITY = "INVALID_QUANTITY"
    QUANTITY_EXCEEDS_AUTHORIZATION = "QUANTITY_EXCEEDS_AUTHORIZATION"
    INVALID_ORDER_TYPE = "INVALID_ORDER_TYPE"
    INVALID_PRICE = "INVALID_PRICE"
    INVALID_TIME_IN_FORCE = "INVALID_TIME_IN_FORCE"
    MISSING_IDEMPOTENCY_KEY = "MISSING_IDEMPOTENCY_KEY"
    MISSING_CORRELATION_ID = "MISSING_CORRELATION_ID"


class OrderRequestValidationError(ValueError):
    """Raised when a request fails validation / normalization.

    Inherits from :class:`ValueError` so callers can keep the generic contract
    while still reading the structured ``errors`` attribute.
    """

    def __init__(
        self,
        errors: Iterable[str],
        *,
        message: Optional[str] = None,
    ) -> None:
        self.errors: Tuple[str, ...] = tuple(errors)
        super().__init__(message or "; ".join(self.errors) or "invalid order request")
