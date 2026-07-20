"""
Optimizer.
"""

from .optimization_result import OptimizationResult


class Optimizer:
    def optimize(
        self,
        trials,
        objective,
    ):
        best = max(
            trials,
            key=lambda t: objective.evaluate(t),
        )
        return OptimizationResult(best_parameters=best)