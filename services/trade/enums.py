"""
Trade enums.
"""

from __future__ import annotations

from enum import Enum


class LiquidityFlag(str, Enum):
    MAKER = "MAKER"
    TAKER = "TAKER"
    UNKNOWN = "UNKNOWN"