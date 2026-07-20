"""
Optimization service.
"""

from .optimizer import Optimizer


class OptimizationService:
    def __init__(
        self,
        optimizer,
    ):
        self.optimizer = optimizer

    def run(
        self,
        trials,
        objective,
    ):
        return self.optimizer.optimize(trials, objective)