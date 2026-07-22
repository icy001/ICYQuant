import pytest

from services.risk import (
    RiskMetric,
    RiskMetricRepository,
    RiskAggregator,
    RiskScoreCalculator,
    RiskAggregationEngine,
)


def test_risk_aggregation():
    repository = RiskMetricRepository()

    repository.save(
        RiskMetric(
            "VAR",
            0.20,
            "VaR",
        )
    )

    repository.save(
        RiskMetric(
            "LEVERAGE",
            0.40,
            "Leverage",
        )
    )

    engine = RiskAggregationEngine(
        repository,
        RiskAggregator(),
        RiskScoreCalculator(),
    )

    result = engine.aggregate()

    assert result.risk_score == pytest.approx(0.30)