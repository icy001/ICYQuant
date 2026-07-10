from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from datetime import datetime

from .bar import Bar
from .types import TimeFrame


class MarketDataProvider(ABC):
    @abstractmethod
    def load_bars(
        self,
        symbol: str,
        timeframe: TimeFrame,
        start: datetime,
        end: datetime,
    ) -> list[Bar]:
        pass