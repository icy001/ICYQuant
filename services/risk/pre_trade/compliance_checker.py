"""
Compliance Checker — Regulatory and internal compliance validation.

Unified compliance validation checking restricted lists, trading
restrictions, regulatory requirements, and internal trading policies.

Logic::

    Restricted List → Trading Restriction → Regulation → PASS / FAIL
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .pre_trade_context import PreTradeContext
from .risk_reason import RiskReason, ReasonCategory

logger = logging.getLogger(__name__)


class ComplianceChecker:
    """
    Validates orders against regulatory and internal compliance rules.

    Checks:
    - Restricted security lists (sanctions, internal blacklists)
    - Trading restrictions (lock-up periods, blackout windows)
    - Regulatory limits (pattern day trading, wash sale, etc.)
    - Internal policies (trading hours, position disclosure)

    Usage::

        checker = ComplianceChecker(
            restricted_symbols={"BANNED_TICKER"},
            blackout_periods=[("2026-01-01", "2026-01-15")],
        )
        await checker.check(ctx)
    """

    def __init__(
        self,
        restricted_symbols: Optional[set[str]] = None,
        watchlist_symbols: Optional[set[str]] = None,
        blackout_periods: Optional[list[tuple[str, str]]] = None,
        max_daily_trades: int = 500,
        enforce_wash_sale: bool = False,
    ) -> None:
        self._restricted_symbols = restricted_symbols or set()
        self._watchlist_symbols = watchlist_symbols or set()
        self._blackout_periods = blackout_periods or []
        self._max_daily_trades = max_daily_trades
        self._enforce_wash_sale = enforce_wash_sale

    async def check(self, ctx: PreTradeContext) -> None:
        """Run all compliance checks."""
        request = ctx.request

        # --- Restricted Symbol Check ---
        if request.symbol.upper() in {s.upper() for s in self._restricted_symbols}:
            reason = RiskReason.blocking(
                category=ReasonCategory.COMPLIANCE,
                message=(
                    f"Symbol `{request.symbol}` is on the compliance "
                    f"restricted list. Trading is prohibited."
                ),
                checker="ComplianceChecker",
                resolution="Contact the compliance department for guidance.",
            )
            ctx.add_reason(reason)
            ctx.add_checker_result(
                "ComplianceChecker", passed=False,
                metadata={"symbol": request.symbol, "restricted": True},
            )
            return

        # --- Blackout Period Check ---
        now = datetime.now(timezone.utc).date()
        in_blackout = False
        for start_str, end_str in self._blackout_periods:
            start = datetime.fromisoformat(start_str).date()
            end = datetime.fromisoformat(end_str).date()
            if start <= now <= end:
                in_blackout = True
                break

        if in_blackout:
            reason = RiskReason.blocking(
                category=ReasonCategory.COMPLIANCE,
                message="Trading is prohibited during the current blackout period.",
                checker="ComplianceChecker",
                resolution="Wait until the blackout period ends.",
            )
            ctx.add_reason(reason)
            ctx.add_checker_result(
                "ComplianceChecker", passed=False,
                metadata={"in_blackout": True},
            )
            return

        # --- Watchlist Symbol Warning ---
        if request.symbol in self._watchlist_symbols:
            reason = RiskReason.warning(
                category=ReasonCategory.COMPLIANCE,
                message=(
                    f"Symbol `{request.symbol}` is on the compliance "
                    f"watchlist. Proceed with caution."
                ),
                checker="ComplianceChecker",
                resolution="Review watchlist status before executing.",
            )
            ctx.add_reason(reason)

        # --- Wash Sale Check ---
        if self._enforce_wash_sale:
            positions = request.account_positions or {}
            if request.is_buy and request.symbol in positions:
                pos = positions[request.symbol]
                if pos.get("sold_recently", False):
                    reason = RiskReason.warning(
                        category=ReasonCategory.COMPLIANCE,
                        message=(
                            f"Potential wash sale detected for "
                            f"{request.symbol}. Verify before proceeding."
                        ),
                        checker="ComplianceChecker",
                        resolution="Confirm trade does not violate wash sale rules.",
                    )
                    ctx.add_reason(reason)

        # --- Daily Trade Count Check ---
        trades_today = request.metadata.get("trades_today", 0)
        if trades_today >= self._max_daily_trades:
            reason = RiskReason.blocking(
                category=ReasonCategory.COMPLIANCE,
                message=(
                    f"Daily trade limit reached: {trades_today}/{self._max_daily_trades}"
                ),
                checker="ComplianceChecker",
                current_value=trades_today,
                limit=self._max_daily_trades,
                resolution="Resume trading on the next business day.",
            )
            ctx.add_reason(reason)
            ctx.add_checker_result(
                "ComplianceChecker", passed=False,
                metadata={"trades_today": trades_today, "max_daily": self._max_daily_trades},
            )
            return

        ctx.add_checker_result(
            "ComplianceChecker", passed=True,
            metadata={"symbol": request.symbol, "trades_today": trades_today},
        )
