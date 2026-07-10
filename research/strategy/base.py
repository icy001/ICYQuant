from abc import ABC, abstractmethod
from typing import Optional, Dict, List

from research.data.bar import Bar

from .signal import Signal, SignalType


class Strategy(ABC):
    def __init__(self):
        self._context = None
        self._broker = None
        self._data_provider = None
        self._initialized = False

    def initialize(self, context, broker, data_provider):
        self._context = context
        self._broker = broker
        self._data_provider = data_provider
        self._initialized = True

    def on_start(self):
        pass

    @abstractmethod
    def on_bar(self, bar: Bar) -> Signal:
        pass

    def on_market(self, market_data: Dict[str, Bar]) -> List[Signal]:
        signals = []
        for symbol, bar in market_data.items():
            signal = self.on_bar(bar)
            if signal:
                signals.append(signal)
        return signals

    def on_order(self, order):
        pass

    def on_fill(self, fill):
        pass

    def on_finish(self):
        pass

    def get_context(self):
        return self._context

    def get_broker(self):
        return self._broker

    def get_data_provider(self):
        return self._data_provider

    def is_initialized(self):
        return self._initialized