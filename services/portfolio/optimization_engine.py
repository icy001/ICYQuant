"""
Portfolio optimization engine.
"""

from decimal import Decimal

from .optimization import OptimizationResult


class PortfolioOptimizationEngine:
    def __init__(
        self,
        optimizer,
        validator,
    ):
        self.optimizer = optimizer
        self.validator = validator

    def run(
        self,
        assets,
        objective,
    ):
        weights = self.optimizer.optimize(assets, objective)

        if not self.validator.validate(weights):
            raise ValueError("invalid weights")

        return OptimizationResult(
            weights={key: Decimal(str(value)) for key, value in weights.items()},
            expected_return=Decimal("0"),
            expected_risk=Decimal("0"),
        )