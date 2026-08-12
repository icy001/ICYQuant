"""
VenueState — the state model of a trading venue (broker / exchange / FIX
session) under Institutional Control (Commit 26 Part 1.4, spec section 7).

The core value of Venue Control is **failure isolation**: a single venue
(NASDAQ) degrading must not take the whole system down — other venues
(NYSE, CME) keep trading.
"""

from __future__ import annotations

from enum import Enum


class VenueState(str, Enum):

    ONLINE = "ONLINE"

    DEGRADED = "DEGRADED"

    PAUSED = "PAUSED"

    DISABLED = "DISABLED"

    FAILOVER = "FAILOVER"

    UNKNOWN = "UNKNOWN"
