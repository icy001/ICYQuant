from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional


class MarketDataProvider(ABC):
    @abstractmethod
    def load_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1D",
    ):
        pass

    @abstractmethod
    def load_tick_data(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ):
        pass