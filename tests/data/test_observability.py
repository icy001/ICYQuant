from services.data import (
    DataQualityMetrics,
)


def test_quality_metrics():

    metrics = DataQualityMetrics()

    assert metrics.calculate(
        100,
        2,
    ) == 0.98