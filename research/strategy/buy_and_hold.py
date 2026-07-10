from research.data.bar import Bar

from .base import Strategy
from .signal import Signal, SignalType


class BuyAndHoldStrategy(Strategy):

    def __init__(self, symbol: str):
        super().__init__()
        self.symbol = symbol
        self.bought = False

    def on_bar(self, bar: Bar) -> Signal:
        if self.bought:
            return Signal(
                symbol=self.symbol,
                signal_type=SignalType.HOLD,
            )

        self.bought = True

        return Signal(
            symbol=self.symbol,
            signal_type=SignalType.BUY,
            strength=1.0,
        )