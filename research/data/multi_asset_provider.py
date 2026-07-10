from datetime import datetime
from typing import Dict, List, Optional

from .bar import Bar
from .provider import MarketDataProvider
from .types import TimeFrame
from .universe import Universe


class MultiAssetDataProvider:

    def __init__(self, providers: Dict[str, MarketDataProvider]):
        self.providers = providers

    def load(
        self,
        universe: Universe,
        timeframe: TimeFrame,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Dict[str, List[Bar]]:
        datasets = {}

        for symbol in universe.symbols:
            if symbol not in self.providers:
                raise ValueError(f"No provider registered for symbol: {symbol}")

            provider = self.providers[symbol]
            datasets[symbol] = provider.load_bars(symbol, timeframe, start, end)

        return datasets

    def register_provider(self, symbol: str, provider: MarketDataProvider):
        self.providers[symbol] = provider

    def get_provider(self, symbol: str) -> Optional[MarketDataProvider]:
        return self.providers.get(symbol)