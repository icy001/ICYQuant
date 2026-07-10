from collections import deque

from research.data.bar import Bar

from .base import Strategy
from .signal import Signal, SignalType


class MovingAverageCrossStrategy(Strategy):

    def __init__(self, symbol: str, short_window: int = 10, long_window: int = 30):
        super().__init__()
        self.symbol = symbol
        self.short = deque(maxlen=short_window)
        self.long = deque(maxlen=long_window)

    def on_bar(self, bar: Bar) -> Signal:
        self.short.append(bar.close)
        self.long.append(bar.close)

        if len(self.long) < self.long.maxlen:
            return Signal(
                symbol=self.symbol,
                signal_type=SignalType.HOLD,
            )

        short_avg = sum(self.short) / len(self.short)
        long_avg = sum(self.long) / len(self.long)

        if short_avg > long_avg:
            return Signal(
                symbol=self.symbol,
                signal_type=SignalType.BUY,
                strength=1.0,
            )

        return Signal(
            symbol=self.symbol,
            signal_type=SignalType.SELL,
            strength=1.0,
        )