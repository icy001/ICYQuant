"""
Strategy learning agent.
"""


class StrategyLearningAgent:

    def learn(
        self,
        feedback,
    ):
        return {
            "learning":
                feedback,
            "updated":
                True
        }