"""Time-in-force (Commit 33 Part 1.1).

Values mirror the order request contract (Commit 32 Part 1.1) so a request and
its order always agree on how long the order stays valid.
"""

from __future__ import annotations

from enum import Enum


class TimeInForce(str, Enum):
    """How long an order remains valid."""

    DAY = "DAY"
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"
