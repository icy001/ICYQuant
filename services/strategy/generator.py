"""
Signal generator.
"""

from __future__ import annotations

from datetime import datetime

from .confidence import Confidence
from .signal_event import SignalEvent
from .signal_type import SignalType


class SignalGenerator:
    def generate(
        self,
        *,
        strategy_id: str,
        symbol: str,
        signal: SignalType,
        confidence: float,
        reason: str,
    ) -> SignalEvent:
        return SignalEvent(
            strategy_id=strategy_id,
            symbol=symbol,
            signal=signal,
            confidence=Confidence(confidence),
            timestamp=datetime.utcnow(),
            reason=reason,
        )