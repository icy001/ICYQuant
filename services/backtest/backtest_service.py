"""
Backtest service.
"""


class BacktestService:

    def __init__(
        self,
        repository,
        factory,
    ):

        self.repository = repository

        self.factory = factory

    def create(
        self,
        strategy_id,
    ):

        backtest = self.factory.create(
            strategy_id
        )

        self.repository.save(
            backtest
        )

        return backtest