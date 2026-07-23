"""
Strategy learning agent.
"""


class StrategyLearningAgent:

    def evaluate(
        self,
        strategy,
        performance,
    ):

        return {
            "strategy": strategy,
            "score": performance,
        }