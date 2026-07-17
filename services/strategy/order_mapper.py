"""
Signal to order mapping.
"""

from __future__ import annotations

from decimal import Decimal

from .command import OrderCommand
from .signal_type import SignalType


class OrderMapper:
    def map(
        self,
        signal,
    ) -> OrderCommand:
        side = (
            "BUY"
            if signal.signal == SignalType.BUY
            else "SELL"
        )

        return OrderCommand(
            strategy_id=signal.strategy_id,
            symbol=signal.symbol,
            side=side,
            quantity=Decimal("1"),
        )