"""
Parameter optimizer.
"""

from .optimizer_result import OptimizationResult


class ParameterOptimizer:
    def __init__(
        self,
        evaluator,
    ):
        self.evaluator = evaluator

    def optimize(
        self,
        candidates,
    ):
        best = None

        for candidate in candidates:
            score = self.evaluator.evaluate(candidate)

            if best is None or score > best.score:
                best = OptimizationResult(
                    parameters=candidate,
                    score=score,
                )

        return best