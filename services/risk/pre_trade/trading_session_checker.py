"""
Trading Session Checker — Validates that trading is within allowed session hours.

Ensures orders are only submitted during the configured trading sessions
for the target exchange and instrument type.

Logic::

    Current Time ∈ Trading Session Hours → PASS / FAIL
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timezone
from typing import Any, Optional

from .pre_trade_context import PreTradeContext
from .risk_reason import RiskReason, ReasonCategory

logger = logging.getLogger(__name__)


class TradingSessionChecker:
    """
    Validates that the order is submitted during an active trading session.

    Supports multiple session configurations per exchange and instrument
    type, with pre-market and after-hours options.

    Usage::

        checker = TradingSessionChecker(
            regular_open=time(9, 30),
            regular_close=time(16, 0),
            timezone_name="America/New_York",
        )
        await checker.check(ctx)
    """

    def __init__(
        self,
        regular_open: time = time(9, 30),
        regular_close: time = time(16, 0),
        allow_pre_market: bool = False,
        pre_market_open: time = time(4, 0),
        allow_after_hours: bool = False,
        after_hours_close: time = time(20, 0),
        timezone_name: str = "America/New_York",
        session_exceptions: Optional[list[str]] = None,
        exchange_sessions: Optional[dict[str, dict[str, Any]]] = None,
    ) -> None:
        self._regular_open = regular_open
        self._regular_close = regular_close
        self._allow_pre_market = allow_pre_market
        self._pre_market_open = pre_market_open
        self._allow_after_hours = allow_after_hours
        self._after_hours_close = after_hours_close
        self._timezone_name = timezone_name
        self._session_exceptions = set(session_exceptions or [])
        self._exchange_sessions = exchange_sessions or {}

    async def check(self, ctx: PreTradeContext) -> None:
        """Check that the current time is within an active trading session."""
        request = ctx.request
        now = datetime.now(timezone.utc)

        # Check if today is a trading day exception (holiday, etc.)
        today_str = now.strftime("%Y-%m-%d")
        if today_str in self._session_exceptions:
            reason = RiskReason.blocking(
                category=ReasonCategory.TRADING_SESSION,
                message=f"No trading session today ({today_str} is a market holiday or exception day).",
                checker="TradingSessionChecker",
                resolution="Wait for the next regular trading session.",
            )
            ctx.add_reason(reason)
            ctx.add_checker_result(
                "TradingSessionChecker", passed=False,
                metadata={"date": today_str, "holiday": True},
            )
            return

        # Check exchange-specific session if configured
        if request.exchange and request.exchange in self._exchange_sessions:
            session_cfg = self._exchange_sessions[request.exchange]
            open_time = session_cfg.get("open", self._regular_open)
            close_time = session_cfg.get("close", self._regular_close)
            pre_open = session_cfg.get("pre_market_open", self._pre_market_open)
            after_close = session_cfg.get("after_hours_close", self._after_hours_close)
            allow_pre = session_cfg.get("allow_pre_market", self._allow_pre_market)
            allow_after = session_cfg.get("allow_after_hours", self._allow_after_hours)
        else:
            open_time = self._regular_open
            close_time = self._regular_close
            pre_open = self._pre_market_open
            after_close = self._after_hours_close
            allow_pre = self._allow_pre_market
            allow_after = self._allow_after_hours

        # Convert to UTC (simplified: assume exchange timezone is the configured one)
        # In production, use pytz/zoneinfo for proper timezone handling
        current_time = now.time()

        in_regular = open_time <= current_time <= close_time
        in_pre_market = allow_pre and pre_open <= current_time < open_time
        in_after_hours = allow_after and close_time < current_time <= after_close

        if in_regular or in_pre_market or in_after_hours:
            session_type = (
                "pre-market" if in_pre_market
                else "after-hours" if in_after_hours
                else "regular"
            )
            ctx.add_checker_result(
                "TradingSessionChecker", passed=True,
                metadata={"session": session_type, "time": str(current_time)},
            )
            return

        # Outside all session windows
        reason = RiskReason.blocking(
            category=ReasonCategory.TRADING_SESSION,
            message=(
                f"Outside trading session hours. Regular hours: "
                f"{open_time}–{close_time}. "
                f"Current time: {current_time}"
            ),
            checker="TradingSessionChecker",
            resolution="Submit the order during regular trading hours.",
        )
        ctx.add_reason(reason)
        ctx.add_checker_result(
            "TradingSessionChecker", passed=False,
            metadata={
                "current_time": str(current_time),
                "regular_open": str(open_time),
                "regular_close": str(close_time),
            },
        )
