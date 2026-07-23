"""
Autonomous backtest loop.
"""


class AIBacktestLoop:

    def __init__(
        self,
        backtest_service,
    ):

        self.backtest_service = backtest_service

    def run(
        self,
        strategy,
    ):

        return self.backtest_service.run(
            strategy
        )