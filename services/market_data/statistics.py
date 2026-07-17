"""
Market statistics.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MarketStatistics:
    received_quotes: int = 0
    cached_quotes: int = 0
    subscribers: int = 0