"""
Order Rate Limiter — Controls order submission rate per account/strategy.

Prevents strategy malfunction or runaway algorithms from flooding the
system with excessive orders.

Logic::

    Requests / Second ≤ Rate Limit → PASS / FAIL
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

from .pre_trade_context import PreTradeContext
from .risk_reason import RiskReason, ReasonCategory

logger = logging.getLogger(__name__)


class OrderRateLimiter:
    """
    Enforces rate limits on order submissions at account and strategy levels.

    Uses a sliding window approach to track request rates and
    blocks on limit breach.

    Usage::

        limiter = OrderRateLimiter(
            max_requests_per_second=10,
            burst_allowance=20,
        )
        await limiter.check(ctx)
    """

    def __init__(
        self,
        max_requests_per_second: float = 10.0,
        burst_allowance: int = 20,
        max_requests_per_minute: int = 500,
        per_strategy_limits: Optional[dict[str, float]] = None,
    ) -> None:
        self._max_rps = max_requests_per_second
        self._burst_allowance = burst_allowance
        self._max_rpm = max_requests_per_minute
        self._per_strategy_limits = per_strategy_limits or {}
        self._window: list[float] = []  # Unix timestamps of recent requests
        self._strategy_windows: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def check(self, ctx: PreTradeContext) -> None:
        """Check and enforce rate limits for the incoming order."""
        request = ctx.request
        now = time.time()

        async with self._lock:
            # Global rate limit (per-second sliding window)
            effective_rps = self._max_rps
            effective_rpm = self._max_rpm

            # Strategy-specific limit override
            strategy_limit = self._per_strategy_limits.get(request.strategy_id)
            if strategy_limit is not None:
                effective_rps = min(effective_rps, strategy_limit)

            # Clean old entries from window (keep last 1 second for RPS, 60s for RPM)
            cutoff_rps = now - 1.0
            cutoff_rpm = now - 60.0
            self._window = [t for t in self._window if t > cutoff_rpm]

            # RPS check
            recent_rps = [t for t in self._window if t > cutoff_rps]
            current_rps = len(recent_rps)

            if current_rps >= self._burst_allowance:
                # Burst allowance exceeded
                reason = RiskReason.blocking(
                    category=ReasonCategory.RATE_LIMIT,
                    message=(
                        f"Rate limit exceeded: {current_rps} requests in "
                        f"the last second (burst limit: {self._burst_allowance})"
                    ),
                    checker="OrderRateLimiter",
                    current_value=current_rps,
                    limit=self._burst_allowance,
                    resolution="Reduce order submission frequency.",
                )
                ctx.add_reason(reason)
                ctx.add_checker_result(
                    "OrderRateLimiter", passed=False,
                    metadata={
                        "current_rps": current_rps,
                        "burst_limit": self._burst_allowance,
                    },
                )
                return

            if current_rps > effective_rps:
                reason = RiskReason.blocking(
                    category=ReasonCategory.RATE_LIMIT,
                    message=(
                        f"Rate limit exceeded: {current_rps} req/s > "
                        f"{effective_rps} req/s allowed"
                    ),
                    checker="OrderRateLimiter",
                    current_value=current_rps,
                    limit=effective_rps,
                    resolution="Reduce order submission frequency.",
                )
                ctx.add_reason(reason)
                ctx.add_checker_result(
                    "OrderRateLimiter", passed=False,
                    metadata={"current_rps": current_rps, "max_rps": effective_rps},
                )
                return

            # RPM check
            if len(self._window) > effective_rpm:
                reason = RiskReason.blocking(
                    category=ReasonCategory.RATE_LIMIT,
                    message=(
                        f"Minute rate limit exceeded: "
                        f"{len(self._window)} req/min > {effective_rpm} limit"
                    ),
                    checker="OrderRateLimiter",
                    current_value=len(self._window),
                    limit=effective_rpm,
                    resolution="Pause strategy and review submission rate.",
                )
                ctx.add_reason(reason)
                ctx.add_checker_result(
                    "OrderRateLimiter", passed=False,
                    metadata={"current_rpm": len(self._window), "max_rpm": effective_rpm},
                )
                return

            # Record this request
            self._window.append(now)

            # Near-limit warning
            if current_rps > effective_rps * 0.8:
                reason = RiskReason.info(
                    category=ReasonCategory.RATE_LIMIT,
                    message=f"Approaching rate limit: {current_rps}/{effective_rps} req/s",
                    checker="OrderRateLimiter",
                )
                ctx.add_reason(reason)

        ctx.add_checker_result(
            "OrderRateLimiter", passed=True,
            metadata={"current_rps": current_rps, "current_rpm": len(self._window)},
        )
