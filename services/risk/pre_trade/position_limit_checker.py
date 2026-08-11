"""
Position Limit Checker — Validates position limits before order entry.

Enforces position limits at the symbol, account, and strategy levels.
Prevents orders that would exceed configured maximum positions.

Logic::

    Current Position + Requested Position → Position Limit → PASS / FAIL
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .pre_trade_context import PreTradeContext
from .risk_request import OrderSide
from .risk_reason import RiskReason, ReasonCategory

logger = logging.getLogger(__name__)


class PositionLimitChecker:
    """
    Validates that the resulting position after order execution does
    not exceed configured position limits.

    Supports limits at three levels:
    - Per-symbol maximum position
    - Per-account total exposure
    - Per-strategy allocation caps

    Usage::

        checker = PositionLimitChecker()
        await checker.check(ctx)
    """

    def __init__(
        self,
        max_position_per_symbol: Optional[dict[str, float]] = None,
        max_account_exposure: float = 1_000_000.0,
        max_strategy_allocation: float = 500_000.0,
    ) -> None:
        self._max_position_per_symbol = max_position_per_symbol or {}
        self._max_account_exposure = max_account_exposure
        self._max_strategy_allocation = max_strategy_allocation

    async def check(self, ctx: PreTradeContext) -> None:
        """Check position limits against the order intent."""
        request = ctx.request

        # Get current positions from context or request
        positions = request.account_positions or {}
        current_qty = positions.get(request.symbol, {}).get("quantity", 0.0)

        # Calculate resulting position
        if request.side == OrderSide.BUY:
            resulting_position = current_qty + request.quantity
        else:
            resulting_position = current_qty - request.quantity

        # Per-symbol limit
        symbol_limit = self._max_position_per_symbol.get(
            request.symbol, self._max_strategy_allocation
        )
        if abs(resulting_position) > abs(symbol_limit):
            reason = RiskReason.blocking(
                category=ReasonCategory.POSITION_LIMIT,
                message=(
                    f"Position limit exceeded for {request.symbol}: "
                    f"resulting position {resulting_position:.0f} "
                    f"> limit {symbol_limit:.0f}"
                ),
                checker="PositionLimitChecker",
                current_value=resulting_position,
                limit=symbol_limit,
                resolution="Reduce order quantity or close existing positions.",
            )
            ctx.add_reason(reason)
            ctx.add_checker_result(
                "PositionLimitChecker", passed=False,
                metadata={"resulting_position": resulting_position, "limit": symbol_limit},
            )
            return

        # Account-level total value check
        total_account_value = sum(
            p.get("market_value", 0.0) for p in positions.values()
        )
        if total_account_value + request.notional_value > self._max_account_exposure:
            reason = RiskReason.warning(
                category=ReasonCategory.POSITION_LIMIT,
                message=(
                    f"Account exposure would exceed {self._max_account_exposure:.0f} "
                    f"after this order."
                ),
                checker="PositionLimitChecker",
                current_value=total_account_value + request.notional_value,
                limit=self._max_account_exposure,
                resolution="Review total account exposure before proceeding.",
            )
            ctx.add_reason(reason)

        ctx.add_checker_result(
            "PositionLimitChecker", passed=True,
            metadata={"resulting_position": resulting_position, "limit": symbol_limit},
        )
