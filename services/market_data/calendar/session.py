"""TradingSession — the unified session object (Commit 005).

TradingCalendar + Instrument → TradingSession.  A session describes
one phase segment of one trading date for one exchange: what phase
the market is in, when the segment starts/ends, and whether
continuous trading is allowed.

Downstream consumers (Strategy, Paper Trading) use
``session.is_tradable`` as the single trade gate instead of
implementing their own time checks.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from ..domain.instrument import Exchange
from .market_phase import PHASE_LABELS, TRADABLE_PHASES, MarketPhase


@dataclass(frozen=True)
class TradingSession:
    """One phase segment of a trading date for one exchange."""

    trading_date: date
    exchange: Exchange
    market: str = "A-SHARE"
    phase: MarketPhase = MarketPhase.NON_TRADING
    session_start: Optional[datetime] = None  # tz-aware, CST
    session_end: Optional[datetime] = None    # tz-aware, CST
    is_trading_day: bool = False

    @property
    def is_tradable(self) -> bool:
        """True only during continuous auction phases on a trading
        day (the Strategy Gate)."""
        return self.is_trading_day and self.phase in TRADABLE_PHASES

    @property
    def phase_label(self) -> str:
        return PHASE_LABELS.get(self.phase.value, self.phase.value)

    def as_dict(self) -> dict:
        return {
            "trading_date": self.trading_date.isoformat(),
            "exchange": self.exchange.value,
            "market": self.market,
            "phase": self.phase.value,
            "phase_label": self.phase_label,
            "session_start": (
                self.session_start.isoformat()
                if self.session_start
                else None
            ),
            "session_end": (
                self.session_end.isoformat() if self.session_end else None
            ),
            "is_trading_day": self.is_trading_day,
            "is_tradable": self.is_tradable,
        }


__all__ = ["TradingSession"]
