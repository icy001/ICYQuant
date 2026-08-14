"""Order request validation.

The :class:`OrderRequestValidator` answers one question: is this order request
legal?  It is strictly read-only - it never rewrites the request (case folding
and symbol trimming belong to the normalizer).  All problems are collected in a
single pass and returned as an :class:`OrderRequestValidationResult`, so the
caller can fix everything at once.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from services.order.request.errors import OrderRequestErrorCode
from services.order.request.model import ORDER_TYPES, TIME_IN_FORCE_VALUES, OrderRequest

#: Sides accepted by the order request domain (case-insensitive).
SIDES = frozenset({"BUY", "SELL"})

#: Time-in-force values compatible with MARKET orders.
MARKET_COMPATIBLE_TIME_IN_FORCE = frozenset({"DAY", "IOC", "FOK"})

#: Identity / lineage fields that must always be non-empty.
LINEAGE_FIELDS = (
    "order_request_id",
    "intent_id",
    "authorization_id",
    "certificate_id",
    "decision_id",
    "strategy_id",
    "session_id",
    "signal_id",
)


@dataclass(frozen=True)
class OrderRequestValidationResult:
    """Aggregated outcome of one validation pass."""

    valid: bool
    errors: tuple = ()


def is_valid_symbol(symbol: str) -> bool:
    """Symbol must be non-blank and free of control characters / inner spaces.

    ``" NVDA "`` trims to ``"NVDA"`` (acceptable); ``"NV DA"`` cannot be
    auto-repaired because that would guess at the instrument identity, and
    ``"\\nNVDA"`` must never reach the OMS.
    """
    if not symbol or not symbol.strip():
        return False
    # Control characters are rejected on the raw string first: a leading
    # "\n" would otherwise be stripped away before the check below runs.
    if any(ord(character) < 32 or ord(character) == 127 for character in symbol):
        return False
    stripped = symbol.strip()
    if " " in stripped or "\t" in stripped:
        return False
    return True


class OrderRequestValidator:
    """Read-only structural validation of an order request.

    ``approved_quantity`` is the risk-approved ceiling: when provided (either
    at construction or per call) the validator enforces ``quantity <=
    approved_quantity``.  The order request layer never re-runs risk; it only
    checks that the request stays inside the authorization.
    """

    def __init__(self, *, approved_quantity: Optional[float] = None) -> None:
        self.approved_quantity = approved_quantity

    def validate(
        self,
        request: Optional[OrderRequest],
        *,
        approved_quantity: Optional[float] = None,
    ) -> OrderRequestValidationResult:
        """Validate the request; returns all problems, never raises."""
        if request is None:
            return OrderRequestValidationResult(valid=False, errors=(OrderRequestErrorCode.INVALID_REQUEST.value,))

        ceiling = self.approved_quantity if approved_quantity is None else approved_quantity
        errors = []

        self._validate_lineage(request, errors)
        self._validate_symbol(request, errors)
        self._validate_side(request, errors)
        self._validate_quantity(request, errors, ceiling)
        self._validate_order_type(request, errors)
        self._validate_price(request, errors)
        self._validate_time_in_force(request, errors)
        self._validate_idempotency(request, errors)

        return OrderRequestValidationResult(
            valid=not errors,
            errors=tuple(errors),
        )

    # --- individual checks --------------------------------------------------

    @staticmethod
    def _validate_lineage(request: OrderRequest, errors: list) -> None:
        for attribute in LINEAGE_FIELDS:
            if not getattr(request, attribute):
                errors.append(OrderRequestErrorCode.MISSING_LINEAGE.value)
                return
        if not request.correlation_id:
            errors.append(OrderRequestErrorCode.MISSING_CORRELATION_ID.value)

    @staticmethod
    def _validate_symbol(request: OrderRequest, errors: list) -> None:
        if not is_valid_symbol(request.symbol):
            errors.append(OrderRequestErrorCode.INVALID_SYMBOL.value)

    @staticmethod
    def _validate_side(request: OrderRequest, errors: list) -> None:
        if not request.side or request.side.strip().upper() not in SIDES:
            errors.append(OrderRequestErrorCode.INVALID_SIDE.value)

    @staticmethod
    def _validate_quantity(
        request: OrderRequest,
        errors: list,
        ceiling: Optional[float],
    ) -> None:
        quantity = request.quantity
        if not isinstance(quantity, (int, float)) or not math.isfinite(float(quantity)) or float(quantity) <= 0:
            errors.append(OrderRequestErrorCode.INVALID_QUANTITY.value)
            return
        if ceiling is not None and float(quantity) > float(ceiling):
            errors.append(OrderRequestErrorCode.QUANTITY_EXCEEDS_AUTHORIZATION.value)

    @staticmethod
    def _validate_order_type(request: OrderRequest, errors: list) -> None:
        if not request.order_type or request.order_type.strip().upper() not in ORDER_TYPES:
            errors.append(OrderRequestErrorCode.INVALID_ORDER_TYPE.value)

    @staticmethod
    def _validate_price(request: OrderRequest, errors: list) -> None:
        order_type = request.order_type.strip().upper() if request.order_type else ""
        price = request.limit_price
        if order_type == "MARKET":
            if price is not None:
                errors.append(OrderRequestErrorCode.INVALID_PRICE.value)
            return
        if order_type == "LIMIT":
            if price is None:
                errors.append(OrderRequestErrorCode.INVALID_PRICE.value)
            elif not isinstance(price, (int, float)) or not math.isfinite(float(price)) or float(price) <= 0:
                errors.append(OrderRequestErrorCode.INVALID_PRICE.value)

    @staticmethod
    def _validate_time_in_force(request: OrderRequest, errors: list) -> None:
        tif = request.time_in_force.strip().upper() if request.time_in_force else ""
        if tif not in TIME_IN_FORCE_VALUES:
            errors.append(OrderRequestErrorCode.INVALID_TIME_IN_FORCE.value)
            return
        order_type = request.order_type.strip().upper() if request.order_type else ""
        if order_type == "MARKET" and tif not in MARKET_COMPATIBLE_TIME_IN_FORCE:
            errors.append(OrderRequestErrorCode.INVALID_TIME_IN_FORCE.value)

    @staticmethod
    def _validate_idempotency(request: OrderRequest, errors: list) -> None:
        if not request.idempotency_key:
            errors.append(OrderRequestErrorCode.MISSING_IDEMPOTENCY_KEY.value)
