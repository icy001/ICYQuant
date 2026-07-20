"""
Strategy evaluator.
"""


class StrategyEvaluator:
    def evaluate(
        self,
        result,
    ):
        return result.get("score", 0)