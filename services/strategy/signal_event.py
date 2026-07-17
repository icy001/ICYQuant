"""
Trading signal event.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .confidence import Confidence
from .signal_type import SignalType


@dataclass(frozen=True)
class SignalEvent:
    strategy_id: str
    symbol: str
    signal: SignalType
    confidence: Confidence
    timestamp: datetime
    reason: str