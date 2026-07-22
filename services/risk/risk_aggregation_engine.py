"""
Risk aggregation engine.
"""

from .unified_risk_view import UnifiedRiskView


class RiskAggregationEngine:

    def __init__(
        self,
        repository,
        aggregator,
        calculator,
    ):

        self.repository = repository

        self.aggregator = aggregator

        self.calculator = calculator

    def aggregate(self):

        metrics = self.aggregator.aggregate(
            self.repository.list_all()
        )

        score = self.calculator.calculate(
            metrics
        )

        return UnifiedRiskView(
            metrics,
            score,
        )