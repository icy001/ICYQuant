"""
Strategy signal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .enums import SignalType


@dataclass(frozen=True)
class StrategySignal:
    symbol: str
    signal_type: SignalType
    price: Decimal
    timestamp: datetime