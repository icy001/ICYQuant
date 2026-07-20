"""
Optimization service.
"""


class OptimizationService:
    def __init__(
        self,
        optimizer,
    ):
        self.optimizer = optimizer

    def run(
        self,
        candidates,
    ):
        return self.optimizer.optimize(candidates)