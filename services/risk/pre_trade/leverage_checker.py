"""
Leverage Checker — Validates leverage ratios before order entry.

Ensures the resulting leverage after order execution does not exceed
configured maximum leverage for the account or strategy.

Logic::

    Total Leverage = Total Exposure / Net Liquidation Value
    Resulting Leverage = (Current Exposure + Order Value) / NLV
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .pre_trade_context import PreTradeContext
from .risk_reason import RiskReason, ReasonCategory

logger = logging.getLogger(__name__)


class LeverageChecker:
    """
    Validates that leverage ratios remain within configured limits.

    Supports:
    - Per-account maximum leverage
    - Per-strategy maximum leverage
    - Per-instrument-type leverage caps

    Usage::

        checker = LeverageChecker(max_leverage=2.0)
        await checker.check(ctx)
    """

    def __init__(
        self,
        max_leverage: float = 2.0,
        max_strategy_leverage: Optional[dict[str, float]] = None,
        max_instrument_leverage: Optional[dict[str, float]] = None,
        net_liquidation_value: float = 100_000.0,
    ) -> None:
        self._max_leverage = max_leverage
        self._max_strategy_leverage = max_strategy_leverage or {}
        self._max_instrument_leverage = max_instrument_leverage or {
            "equity": 2.0,
            "etf": 2.0,
            "future": 10.0,
            "option": 5.0,
            "forex": 50.0,
            "crypto": 3.0,
        }
        self._nlv = net_liquidation_value

    async def check(self, ctx: PreTradeContext) -> None:
        """Check leverage limits against the order intent."""
        request = ctx.request
        positions = request.account_positions or {}
        market = request.market_data or {}

        # Calculate current total exposure
        current_exposure = 0.0
        for pos in positions.values():
            qty = pos.get("quantity", 0.0)
            price = pos.get("avg_price", 0.0)
            current_exposure += abs(qty) * price

        # Add pending order value
        instrument_price = market.get("price", request.price or 0.0)
        order_exposure = request.quantity * instrument_price
        total_exposure = current_exposure + order_exposure

        # Get NLV from market data or use default
        nlv = market.get("nlv", self._nlv)
        if nlv <= 0:
            nlv = self._nlv

        resulting_leverage = total_exposure / nlv

        # Account-level check
        max_lev = self._max_leverage
        strategy_max = self._max_strategy_leverage.get(
            request.strategy_id, self._max_leverage
        )
        instrument_max = self._max_instrument_leverage.get(
            request.instrument_type.value, self._max_leverage
        )
        effective_max = min(max_lev, strategy_max, instrument_max)

        if resulting_leverage > effective_max:
            reason = RiskReason.blocking(
                category=ReasonCategory.LEVERAGE,
                message=(
                    f"Leverage limit exceeded: resulting leverage "
                    f"{resulting_leverage:.2f}x > {effective_max:.2f}x max"
                ),
                checker="LeverageChecker",
                current_value=resulting_leverage,
                limit=effective_max,
                resolution="Reduce order size or increase account equity.",
            )
            ctx.add_reason(reason)
            ctx.add_checker_result(
                "LeverageChecker", passed=False,
                metadata={
                    "resulting_leverage": resulting_leverage,
                    "max_leverage": effective_max,
                    "current_exposure": current_exposure,
                },
            )
            return

        # Warning if approaching limit
        if resulting_leverage > effective_max * 0.85:
            reason = RiskReason.warning(
                category=ReasonCategory.LEVERAGE,
                message=(
                    f"Leverage approaching limit: {resulting_leverage:.2f}x "
                    f"/ {effective_max:.2f}x"
                ),
                checker="LeverageChecker",
                current_value=resulting_leverage,
                limit=effective_max,
            )
            ctx.add_reason(reason)

        ctx.add_checker_result(
            "LeverageChecker", passed=True,
            metadata={
                "resulting_leverage": resulting_leverage,
                "max_leverage": effective_max,
            },
        )
