"""
Strategy runner.
"""


class StrategyRunner:
    async def run(
        self,
        strategy,
        market_event,
    ):
        return strategy.on_event(market_event)