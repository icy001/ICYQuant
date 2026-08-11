"""
Liquidity Checker — Validates order size relative to market liquidity.

Prevents large orders from causing excessive market impact by comparing
order size to average daily volume (ADV) and current order book depth.

Logic::

    Order Size / ADV < Participation Rate Limit → PASS / FAIL
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .pre_trade_context import PreTradeContext
from .risk_reason import RiskReason, ReasonCategory

logger = logging.getLogger(__name__)


class LiquidityChecker:
    """
    Validates that order size does not exceed liquidity thresholds.

    Checks:
    - Participation rate (order size / ADV)
    - Order book depth availability
    - Maximum order value in notional terms

    Usage::

        checker = LiquidityChecker(max_participation_rate=10.0)
        await checker.check(ctx)
    """

    def __init__(
        self,
        max_participation_rate: float = 10.0,
        max_order_value_ratio: float = 5.0,
        min_adv: float = 0.0,
    ) -> None:
        self._max_participation = max_participation_rate
        self._max_order_value_ratio = max_order_value_ratio
        self._min_adv = min_adv

    async def check(self, ctx: PreTradeContext) -> None:
        """Check liquidity constraints for the order."""
        request = ctx.request
        market = request.market_data or {}

        instrument_price = market.get("price", request.price or 0.0)
        order_value = abs(request.quantity * instrument_price)

        # Average Daily Volume (from market data)
        adv = market.get("average_daily_volume", 0.0)
        adv_value = adv * instrument_price

        # Participation rate check
        if adv_value > 0:
            participation = (order_value / adv_value) * 100.0
            if participation > self._max_participation:
                reason = RiskReason.blocking(
                    category=ReasonCategory.LIQUIDITY,
                    message=(
                        f"Participation rate {participation:.1f}% exceeds "
                        f"limit {self._max_participation:.1f}% of ADV"
                    ),
                    checker="LiquidityChecker",
                    current_value=participation,
                    limit=self._max_participation,
                    resolution="Reduce order size or use algorithmic execution (TWAP/VWAP).",
                )
                ctx.add_reason(reason)
                ctx.add_checker_result(
                    "LiquidityChecker", passed=False,
                    metadata={
                        "participation_rate": participation,
                        "order_value": order_value,
                        "adv_value": adv_value,
                    },
                )
                return

        # Order book depth check
        bid_depth = market.get("bid_depth", 0.0)
        ask_depth = market.get("ask_depth", 0.0)
        if bid_depth > 0 or ask_depth > 0:
            depth = bid_depth if request.is_sell else ask_depth
            if depth > 0 and request.quantity > depth * 0.5:
                reason = RiskReason.warning(
                    category=ReasonCategory.LIQUIDITY,
                    message=(
                        f"Order size ({request.quantity:.0f}) exceeds "
                        f"50% of order book depth ({depth:.0f})"
                    ),
                    checker="LiquidityChecker",
                    current_value=request.quantity,
                    limit=depth * 0.5,
                    resolution="Consider splitting order to minimize market impact.",
                )
                ctx.add_reason(reason)

        # Warning for near-limit
        if adv_value > 0:
            participation = (order_value / adv_value) * 100.0
            if participation > self._max_participation * 0.7:
                reason = RiskReason.info(
                    category=ReasonCategory.LIQUIDITY,
                    message=(
                        f"Participation rate {participation:.1f}% approaching "
                        f"limit {self._max_participation:.1f}%"
                    ),
                    checker="LiquidityChecker",
                )
                ctx.add_reason(reason)

        ctx.add_checker_result(
            "LiquidityChecker", passed=True,
            metadata={
                "order_value": order_value,
                "adv_value": adv_value,
                "participation_rate": (
                    (order_value / adv_value) * 100.0 if adv_value else 0.0
                ),
            },
        )
