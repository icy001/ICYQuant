"""
Monte Carlo engine.
"""

from .monte_carlo_result import (
    MonteCarloResult,
)


class MonteCarloEngine:

    def __init__(
        self,
        generator,
        analyzer,
        ci,
    ):

        self.generator = generator

        self.analyzer = analyzer

        self.ci = ci


    def simulate(
        self,
        sampler,
        returns,
        iterations,
    ):

        simulations = list(
            self.generator.generate(
                sampler,
                returns,
                iterations,
            )
        )

        distribution = self.analyzer.analyze(
            simulations,
        )

        interval = self.ci.calculate(
            distribution,
        )

        return MonteCarloResult(
            iterations=iterations,
            mean_return=
                sum(distribution)
                / len(distribution),
            confidence_interval=
                interval,
        )