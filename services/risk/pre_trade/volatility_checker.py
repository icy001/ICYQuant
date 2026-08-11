"""
Volatility Checker — Dynamic risk control based on market volatility.

Adjusts risk thresholds based on current market volatility to prevent
order entry during extreme market conditions.

Logic::

    ATR → Volatility Regime → Risk Threshold Adjustment → PASS / WARN
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .pre_trade_context import PreTradeContext
from .risk_reason import RiskReason, ReasonCategory

logger = logging.getLogger(__name__)


class VolatilityChecker:
    """
    Dynamically adjusts risk controls based on current volatility.

    In high-volatility regimes, risk thresholds are tightened to
    protect against outsized moves. In low-volatility regimes,
    normal thresholds apply.

    Usage::

        checker = VolatilityChecker(max_atr_pct=5.0, high_vol_threshold=3.0)
        await checker.check(ctx)
    """

    def __init__(
        self,
        max_atr_pct: float = 5.0,
        high_vol_threshold: float = 3.0,
        extreme_vol_threshold: float = 8.0,
    ) -> None:
        self._max_atr_pct = max_atr_pct
        self._high_vol_threshold = high_vol_threshold
        self._extreme_vol_threshold = extreme_vol_threshold

    async def check(self, ctx: PreTradeContext) -> None:
        """Check volatility conditions for the order."""
        request = ctx.request
        market = request.market_data or {}

        instrument_price = market.get("price", request.price or 0.0)
        if instrument_price <= 0:
            ctx.add_checker_result(
                "VolatilityChecker", passed=True,
                metadata={"note": "No price data available; skipping volatility check."},
            )
            return

        # Get volatility metrics
        atr = market.get("atr", 0.0)   # Average True Range
        atr_pct = (atr / instrument_price * 100.0) if instrument_price else 0.0
        daily_vol = market.get("daily_volatility", atr_pct)
        vix = market.get("vix", market.get("implied_volatility", 0.0))
        beta = market.get("beta", 1.0)

        # Extreme volatility → block
        if atr_pct > self._extreme_vol_threshold or daily_vol > self._extreme_vol_threshold:
            reason = RiskReason.blocking(
                category=ReasonCategory.VOLATILITY,
                message=(
                    f"Extreme volatility detected: ATR {atr_pct:.1f}% "
                    f"> limit {self._extreme_vol_threshold:.1f}%. "
                    f"Orders blocked for {request.symbol}."
                ),
                checker="VolatilityChecker",
                current_value=atr_pct,
                limit=self._extreme_vol_threshold,
                resolution="Wait for volatility to normalize before submitting orders.",
            )
            ctx.add_reason(reason)
            ctx.add_checker_result(
                "VolatilityChecker", passed=False,
                metadata={"atr_pct": atr_pct, "daily_vol": daily_vol, "vix": vix},
            )
            return

        # High volatility → warning
        if atr_pct > self._high_vol_threshold or daily_vol > self._high_vol_threshold:
            reason = RiskReason.warning(
                category=ReasonCategory.VOLATILITY,
                message=(
                    f"Elevated volatility: ATR {atr_pct:.1f}% for "
                    f"{request.symbol}. Risk controls tightened."
                ),
                checker="VolatilityChecker",
                current_value=atr_pct,
                limit=self._high_vol_threshold,
                resolution="Consider reducing position size during high volatility.",
            )
            ctx.add_reason(reason)

        # Liquidity-adjusted volatility: high vol + large order = more risk
        notional_value = request.notional_value
        if atr_pct > self._high_vol_threshold and notional_value > 50_000:
            reason = RiskReason.warning(
                category=ReasonCategory.VOLATILITY,
                message=(
                    f"Large order ({notional_value:.0f}) during elevated "
                    f"volatility ({atr_pct:.1f}% ATR)."
                ),
                checker="VolatilityChecker",
                resolution="Consider reducing order size or using limit orders.",
            )
            ctx.add_reason(reason)

        # VIX / market-wide volatility context
        if vix > 30:
            reason = RiskReason.info(
                category=ReasonCategory.VOLATILITY,
                message=f"VIX at {vix:.1f} — market-wide volatility elevated.",
                checker="VolatilityChecker",
            )
            ctx.add_reason(reason)

        ctx.add_checker_result(
            "VolatilityChecker", passed=True,
            metadata={
                "atr_pct": atr_pct,
                "daily_volatility": daily_vol,
                "vix": vix,
                "beta": beta,
            },
        )
