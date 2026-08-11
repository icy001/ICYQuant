"""
Market Status Checker — Validates market conditions for order entry.

Ensures the target market is open, not halted, and has valid pricing
before accepting orders. Prevents trading during circuit breakers,
trading halts, or pricing anomalies.

Logic::

    Market Open → Not Halted → Price Valid → PASS / FAIL
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .pre_trade_context import PreTradeContext
from .risk_reason import RiskReason, ReasonCategory

logger = logging.getLogger(__name__)


class MarketStatusChecker:
    """
    Validates market conditions before accepting orders.

    Checks:
    - Market open/closed status
    - Symbol-level trading halts
    - Circuit breaker status
    - Price validity (non-zero, non-stale)
    - Spread reasonability

    Usage::

        checker = MarketStatusChecker()
        await checker.check(ctx)
    """

    def __init__(
        self,
        max_spread_pct: float = 5.0,
        max_price_staleness_seconds: float = 60.0,
    ) -> None:
        self._max_spread_pct = max_spread_pct
        self._max_price_staleness = max_price_staleness_seconds

    async def check(self, ctx: PreTradeContext) -> None:
        """Validate market status for the target instrument."""
        request = ctx.request
        market = request.market_data or {}

        # --- Market Status ---
        market_status = market.get("status", "OPEN")
        if market_status in ("CLOSED", "HALTED"):
            reason = RiskReason.blocking(
                category=ReasonCategory.MARKET_STATUS,
                message=f"Market is {market_status}. Cannot accept orders.",
                checker="MarketStatusChecker",
                resolution=f"Wait for market to reopen.",
            )
            ctx.add_reason(reason)
            ctx.add_checker_result(
                "MarketStatusChecker", passed=False,
                metadata={"market_status": market_status},
            )
            return

        # --- Symbol Halt Check ---
        symbol_status = market.get("symbol_status", "ACTIVE")
        if symbol_status in ("HALTED", "SUSPENDED", "DELISTED"):
            reason = RiskReason.blocking(
                category=ReasonCategory.MARKET_STATUS,
                message=(
                    f"Symbol `{request.symbol}` is {symbol_status}. "
                    f"Cannot accept orders."
                ),
                checker="MarketStatusChecker",
                resolution="Wait for the halt to be lifted or contact the exchange.",
            )
            ctx.add_reason(reason)
            ctx.add_checker_result(
                "MarketStatusChecker", passed=False,
                metadata={
                    "symbol": request.symbol,
                    "symbol_status": symbol_status,
                },
            )
            return

        # --- Circuit Breaker Check ---
        if market.get("circuit_breaker", False):
            reason = RiskReason.blocking(
                category=ReasonCategory.MARKET_STATUS,
                message=f"Circuit breaker triggered. All trading halted.",
                checker="MarketStatusChecker",
                resolution="Wait for circuit breaker to be lifted.",
            )
            ctx.add_reason(reason)
            ctx.add_checker_result(
                "MarketStatusChecker", passed=False,
                metadata={"circuit_breaker": True},
            )
            return

        # --- Price Validity ---
        price = market.get("price", request.price)
        if price is None or price <= 0:
            reason = RiskReason.blocking(
                category=ReasonCategory.MARKET_STATUS,
                message=(
                    f"No valid price available for `{request.symbol}`. "
                    f"Cannot evaluate order."
                ),
                checker="MarketStatusChecker",
                resolution="Wait for a valid price quote before submitting.",
            )
            ctx.add_reason(reason)
            ctx.add_checker_result(
                "MarketStatusChecker", passed=False,
                metadata={"price": price},
            )
            return

        # --- Price Staleness ---
        from datetime import datetime, timezone

        price_timestamp = market.get("price_timestamp")
        if price_timestamp:
            try:
                price_time = datetime.fromisoformat(price_timestamp)
                age_seconds = (datetime.now(timezone.utc) - price_time).total_seconds()
                if age_seconds > self._max_price_staleness:
                    reason = RiskReason.warning(
                        category=ReasonCategory.MARKET_STATUS,
                        message=(
                            f"Price for `{request.symbol}` is stale "
                            f"({age_seconds:.0f}s old > {self._max_price_staleness:.0f}s limit)"
                        ),
                        checker="MarketStatusChecker",
                        current_value=age_seconds,
                        limit=self._max_price_staleness,
                        resolution="Wait for a fresh price quote.",
                    )
                    ctx.add_reason(reason)
            except (ValueError, TypeError):
                pass

        # --- Spread Check ---
        bid = market.get("bid", 0.0)
        ask = market.get("ask", 0.0)
        if bid > 0 and ask > 0:
            spread_pct = ((ask - bid) / ((bid + ask) / 2)) * 100.0
            if spread_pct > self._max_spread_pct:
                reason = RiskReason.warning(
                    category=ReasonCategory.MARKET_STATUS,
                    message=(
                        f"Bid-ask spread {spread_pct:.2f}% exceeds "
                        f"limit {self._max_spread_pct:.1f}%"
                    ),
                    checker="MarketStatusChecker",
                    current_value=spread_pct,
                    limit=self._max_spread_pct,
                    resolution="Wait for spread to narrow before executing.",
                )
                ctx.add_reason(reason)

        ctx.add_checker_result(
            "MarketStatusChecker", passed=True,
            metadata={
                "market_status": market_status,
                "symbol": request.symbol,
                "symbol_status": symbol_status,
            },
        )
