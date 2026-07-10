from typing import List

from research.backtest.event_loop import MultiAssetEventLoop
from research.backtest.execution import PortfolioExecutor
from research.events.market import MarketEvent
from research.portfolio.portfolio import Portfolio


class MultiAssetBacktestRunner:

    def __init__(
        self,
        strategy,
        initial_cash: float = 100000.0
    ):
        self.portfolio = Portfolio(initial_cash=initial_cash)
        self.executor = PortfolioExecutor()
        self.loop = MultiAssetEventLoop(
            strategy=strategy,
            executor=self.executor,
            portfolio=self.portfolio
        )

    def run(self, events: List[MarketEvent]) -> Portfolio:
        for event in events:
            self.loop.on_event(event)

        return self.portfolio