"""A-share market phase definitions (Commit 005).

A trading day is divided into phases (China Standard Time)::

    00:00 ─ 09:20   PRE_OPEN       (pre-market, incl. 09:15 call window)
    09:20 ─ 09:30   AUCTION        (opening auction, no cancellation)
    09:30 ─ 11:30   CONTINUOUS_AM  (morning continuous auction)
    11:30 ─ 13:00   LUNCH_BREAK    (midday recess)
    13:00 ─ 15:00   CONTINUOUS_PM  (afternoon continuous auction)
    15:00 ─ 15:05   CLOSE          (market close)
    15:05 ─ 24:00   POST_CLOSE     (post market)

Non-trading days (weekends without makeup, holidays) are NON_TRADING.
"""
from __future__ import annotations

from enum import Enum


class MarketPhase(str, Enum):
    PRE_OPEN = "PRE_OPEN"
    AUCTION = "AUCTION"
    CONTINUOUS_AM = "CONTINUOUS_AM"
    LUNCH_BREAK = "LUNCH_BREAK"
    CONTINUOUS_PM = "CONTINUOUS_PM"
    CLOSE = "CLOSE"
    POST_CLOSE = "POST_CLOSE"
    NON_TRADING = "NON_TRADING"


PHASE_LABELS: dict[str, str] = {
    MarketPhase.PRE_OPEN.value: "Pre-Open",
    MarketPhase.AUCTION.value: "Opening Auction",
    MarketPhase.CONTINUOUS_AM.value: "Continuous Auction (AM)",
    MarketPhase.LUNCH_BREAK.value: "Lunch Break",
    MarketPhase.CONTINUOUS_PM.value: "Continuous Auction (PM)",
    MarketPhase.CLOSE.value: "Market Close",
    MarketPhase.POST_CLOSE.value: "Post Market",
    MarketPhase.NON_TRADING.value: "Non-Trading Day",
}

# Phases where continuous trading is allowed — the Strategy Gate:
# strategies / paper trading only act inside these phases.
TRADABLE_PHASES = frozenset(
    {MarketPhase.CONTINUOUS_AM, MarketPhase.CONTINUOUS_PM}
)

# Phases where 1m bars are aggregated.  Lunch break, pre-open,
# auction, post-close and non-trading days produce no bars.
BAR_PHASES = frozenset(
    {MarketPhase.CONTINUOUS_AM, MarketPhase.CONTINUOUS_PM}
)


__all__ = [
    "MarketPhase",
    "PHASE_LABELS",
    "TRADABLE_PHASES",
    "BAR_PHASES",
]
