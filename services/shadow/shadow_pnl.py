"""Shadow PnL — equity, daily anchor and drawdown (Commit 016 §23).

PnL is *marked*, not booked: equity = shadow cash + marked market
value of the shadow book, total PnL = equity − initial capital.  The
daily anchor resets on the CST trading date, and drawdown is measured
from the peak equity ever marked.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

_CST = timezone(timedelta(hours=8))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _day_key(now: datetime) -> str:
    """CST trading date (naive timestamps are treated as UTC)."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(_CST).date().isoformat()


class ShadowPnL:
    """Marks equity; anchors daily PnL; tracks peak / drawdown."""

    def __init__(self, initial_capital: Decimal | int | str) -> None:
        self.initial_capital = Decimal(str(initial_capital))
        self.peak_equity = Decimal(str(initial_capital))
        self._day = ""
        self._day_start_equity = Decimal(str(initial_capital))

    def mark(self, equity: Decimal | int | str, now: datetime) -> None:
        """Update the daily anchor and the running peak."""
        value = Decimal(str(equity))
        day = _day_key(now)
        if day != self._day:
            # First observation of a new trading day anchors daily PnL.
            self._day = day
            self._day_start_equity = value
        if value > self.peak_equity:
            self.peak_equity = value

    def snapshot(
        self,
        *,
        cash: Decimal | int | str,
        market_value: Decimal | int | str,
        realized_pnl: Decimal | int | str,
        now: datetime,
    ) -> dict:
        """The §23 PnL card, marking the book before computing it."""
        cash = Decimal(str(cash))
        market_value = Decimal(str(market_value))
        realized = Decimal(str(realized_pnl))
        equity = cash + market_value
        self.mark(equity, now)
        total_pnl = equity - self.initial_capital
        daily_pnl = equity - self._day_start_equity
        # Unrealized = total − realized keeps the identity
        # total = realized + unrealized exact even with clipped fills.
        unrealized = total_pnl - realized
        drawdown = (
            (self.peak_equity - equity) / self.peak_equity
            if self.peak_equity > 0
            else Decimal("0")
        )
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return {
            "initial_capital": str(self.initial_capital),
            "cash": str(cash),
            "market_value": str(market_value),
            "equity": str(equity),
            "realized_pnl": str(realized),
            "unrealized_pnl": str(unrealized),
            "daily_pnl": str(daily_pnl),
            "total_pnl": str(total_pnl),
            "peak_equity": str(self.peak_equity),
            "drawdown": str(drawdown),
            "day": self._day,
            "timestamp": now.isoformat(),
        }


__all__ = ["ShadowPnL"]
