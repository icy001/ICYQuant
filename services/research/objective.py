"""
Optimization objective.
"""


class ObjectiveFunction:
    def evaluate(
        self,
        metrics: dict,
    ) -> float:
        return metrics.get("sharpe", 0.0)