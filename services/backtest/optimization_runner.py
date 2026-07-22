"""
Optimization runner.
"""

from .optimization_result import (
    OptimizationResult,
)


class OptimizationRunner:

    def __init__(
        self,
        repository,
    ):

        self.repository = repository


    def evaluate(
        self,
        parameters,
        score,
    ):

        result = OptimizationResult(
            parameters,
            score,
        )

        self.repository.save(
            result,
        )

        return result