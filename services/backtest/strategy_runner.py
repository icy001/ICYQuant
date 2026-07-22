"""
Strategy runner.
"""


class StrategyRunner:

    def __init__(
        self,
        strategy,
    ):

        self.strategy = strategy


    def run(
        self,
        tick,
    ):

        return self.strategy.on_tick(
            tick
        )