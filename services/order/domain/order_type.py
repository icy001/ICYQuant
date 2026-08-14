"""Order type (Commit 33 Part 1.1).

The core domain stays intentionally small: MARKET and LIMIT only.  STOP /
STOP_LIMIT / TRAILING_STOP can be added later without touching the existing
orders.
"""

from __future__ import annotations

from enum import Enum


class OrderType(str, Enum):
    """Order execution type."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
