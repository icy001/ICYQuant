"""Order side (Commit 33 Part 1.1).

An order side is the *direction* of the order: BUY or SELL.  LONG / SHORT are
position / exposure semantics and must never be used as an order side.
"""

from __future__ import annotations

from enum import Enum


class OrderSide(str, Enum):
    """Direction of an order."""

    BUY = "BUY"
    SELL = "SELL"
