"""
Self improving research loop.
"""


class SelfImprovingResearchLoop:

    def __init__(
        self,
        discovery,
        generator,
        backtest,
        ranking,
    ):

        self.discovery = discovery

        self.generator = generator

        self.backtest = backtest

        self.ranking = ranking

    def execute(
        self,
        objective,
    ):

        alpha = self.discovery.discover(
            objective
        )

        strategy = self.generator.generate(
            alpha
        )

        result = self.backtest.run(
            strategy
        )

        return self.ranking.rank(
            result
        )