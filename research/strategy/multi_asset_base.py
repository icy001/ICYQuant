from abc import ABC, abstractmethod
from typing import List

from research.data.snapshot import MarketSnapshot
from research.orders.signal import PortfolioSignal


class MultiAssetStrategy(ABC):

    def __init__(self):
        self._initialized = False

    def initialize(self):
        self._initialized = True

    def on_start(self):
        pass

    @abstractmethod
    def on_market(self, snapshot: MarketSnapshot) -> List[PortfolioSignal]:
        pass

    def on_finish(self):
        pass

    def is_initialized(self):
        return self._initialized