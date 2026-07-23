"""
Strategy adaptation manager.
"""


class StrategyAdaptationManager:

    def adapt(
        self,
        strategy,
        feedback,
    ):

        return {
            "strategy": strategy,
            "feedback": feedback,
            "version": "next",
        }