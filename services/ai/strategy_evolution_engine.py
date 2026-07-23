"""
Strategy evolution engine.
"""


class StrategyEvolutionEngine:

    def evolve(
        self,
        strategy,
        feedback,
    ):

        return {
            "parent": strategy,
            "mutation": feedback,
        }