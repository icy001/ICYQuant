from services.metrics import *


def test_metrics():

    service = MetricsService(
        MetricsRepository(),
        MetricsAggregator()
    )

    service.record(
        Metric(
            "ORDER_COUNT",
            100,
            MetricType.COUNTER
        )
    )

    result = service.summarize()

    assert result == 100
