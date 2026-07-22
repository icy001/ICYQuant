"""
Backtest repository.
"""


class BacktestRepository:

    def __init__(self):

        self.backtests = {}

    def save(
        self,
        backtest,
    ):

        self.backtests[
            backtest.backtest_id
        ] = backtest

    def load(
        self,
        backtest_id,
    ):

        return self.backtests.get(
            backtest_id
        )

    def list_all(self):

        return list(
            self.backtests.values()
        )