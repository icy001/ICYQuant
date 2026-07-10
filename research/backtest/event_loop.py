from typing import Dict

from research.events.market import MarketEvent


class MultiAssetEventLoop:

    def __init__(
        self,
        strategy,
        executor,
        portfolio
    ):
        self.strategy = strategy
        self.executor = executor
        self.portfolio = portfolio

    def on_event(
        self,
        event: MarketEvent
    ) -> None:
        signals = self.strategy.on_market(event.snapshot)

        prices = {
            symbol: bar.close
            for symbol, bar in event.snapshot.bars.items()
        }

        self.executor.rebalance(
            signals,
            prices,
            self.portfolio
        )