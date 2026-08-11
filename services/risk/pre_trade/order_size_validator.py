"""
Order Size Validator — Validates order quantity against configured limits.

Enforces minimum/maximum order sizes, lot size requirements, and
notional value constraints at the per-symbol and per-instrument level.

Logic::

    Min Size ≤ Order Qty ≤ Max Size → PASS / FAIL
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .pre_trade_context import PreTradeContext
from .risk_reason import RiskReason, ReasonCategory

logger = logging.getLogger(__name__)


class OrderSizeValidator:
    """
    Validates that order quantity falls within allowed size bounds.

    Checks:
    - Minimum order quantity
    - Maximum order quantity
    - Lot size / round-lot requirements
    - Minimum and maximum notional value

    Usage::

        validator = OrderSizeValidator(min_qty=1, max_qty=100000, lot_size=100)
        await validator.check(ctx)
    """

    def __init__(
        self,
        min_qty: float = 1.0,
        max_qty: float = 1_000_000.0,
        lot_size: float = 1.0,
        min_notional: float = 0.0,
        max_notional: float = 10_000_000.0,
        symbol_overrides: Optional[dict[str, dict[str, float]]] = None,
    ) -> None:
        self._min_qty = min_qty
        self._max_qty = max_qty
        self._lot_size = lot_size
        self._min_notional = min_notional
        self._max_notional = max_notional
        self._symbol_overrides = symbol_overrides or {}

    async def check(self, ctx: PreTradeContext) -> None:
        """Validate order size boundaries."""
        request = ctx.request
        symbol = request.symbol

        # Apply per-symbol overrides if configured
        overrides = self._symbol_overrides.get(symbol, {})
        min_qty = overrides.get("min_qty", self._min_qty)
        max_qty = overrides.get("max_qty", self._max_qty)
        lot_size = overrides.get("lot_size", self._lot_size)
        min_notional = overrides.get("min_notional", self._min_notional)
        max_notional = overrides.get("max_notional", self._max_notional)

        qty = request.quantity
        notional = request.notional_value

        # Minimum quantity check
        if qty < min_qty:
            reason = RiskReason.blocking(
                category=ReasonCategory.ORDER_SIZE,
                message=(
                    f"Order quantity {qty:.0f} is below minimum "
                    f"allowed quantity {min_qty:.0f}"
                ),
                checker="OrderSizeValidator",
                current_value=qty,
                limit=min_qty,
                resolution=f"Increase order quantity to at least {min_qty:.0f}.",
            )
            ctx.add_reason(reason)
            ctx.add_checker_result(
                "OrderSizeValidator", passed=False,
                metadata={"quantity": qty, "min_qty": min_qty},
            )
            return

        # Maximum quantity check
        if qty > max_qty:
            reason = RiskReason.blocking(
                category=ReasonCategory.ORDER_SIZE,
                message=(
                    f"Order quantity {qty:.0f} exceeds maximum "
                    f"allowed quantity {max_qty:.0f}"
                ),
                checker="OrderSizeValidator",
                current_value=qty,
                limit=max_qty,
                resolution=f"Reduce order quantity to at most {max_qty:.0f}.",
            )
            ctx.add_reason(reason)
            ctx.add_checker_result(
                "OrderSizeValidator", passed=False,
                metadata={"quantity": qty, "max_qty": max_qty},
            )
            return

        # Lot size check
        if lot_size > 1 and qty % lot_size != 0:
            reason = RiskReason.blocking(
                category=ReasonCategory.ORDER_SIZE,
                message=(
                    f"Order quantity {qty:.0f} must be a multiple "
                    f"of lot size {lot_size:.0f}"
                ),
                checker="OrderSizeValidator",
                current_value=qty,
                limit=lot_size,
                resolution=f"Round quantity to the nearest lot size multiple.",
            )
            ctx.add_reason(reason)
            ctx.add_checker_result(
                "OrderSizeValidator", passed=False,
                metadata={"quantity": qty, "lot_size": lot_size},
            )
            return

        # Notional value checks
        if notional > 0:
            if min_notional > 0 and notional < min_notional:
                reason = RiskReason.blocking(
                    category=ReasonCategory.ORDER_SIZE,
                    message=(
                        f"Notional value {notional:.2f} below minimum "
                        f"{min_notional:.2f}"
                    ),
                    checker="OrderSizeValidator",
                    current_value=notional,
                    limit=min_notional,
                    resolution=f"Increase order size to meet minimum notional.",
                )
                ctx.add_reason(reason)
                ctx.add_checker_result(
                    "OrderSizeValidator", passed=False,
                    metadata={"notional": notional, "min_notional": min_notional},
                )
                return

            if max_notional > 0 and notional > max_notional:
                reason = RiskReason.blocking(
                    category=ReasonCategory.ORDER_SIZE,
                    message=(
                        f"Notional value {notional:.2f} exceeds maximum "
                        f"{max_notional:.2f}"
                    ),
                    checker="OrderSizeValidator",
                    current_value=notional,
                    limit=max_notional,
                    resolution=f"Reduce order size to stay within notional limit.",
                )
                ctx.add_reason(reason)
                ctx.add_checker_result(
                    "OrderSizeValidator", passed=False,
                    metadata={"notional": notional, "max_notional": max_notional},
                )
                return

        ctx.add_checker_result(
            "OrderSizeValidator", passed=True,
            metadata={
                "quantity": qty,
                "notional": notional,
                "lot_size": lot_size,
            },
        )
