from services.observability import *


def test_observability():

    collector = MetricCollector()

    service = ObservabilityService(
        collector
    )

    metric = Metric(

        "ORDER_LATENCY",

        20,

        "2026-01-01"

    )

    service.record(metric)

    result = collector.all()

    assert len(result) == 1
