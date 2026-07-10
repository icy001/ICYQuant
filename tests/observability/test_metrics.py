from services.observability import (
    MetricsCollector,
)


def test_metrics_increment():
    metrics = MetricsCollector()
    metrics.increment(
        "orders"
    )
    metrics.increment(
        "orders"
    )
    assert (
        metrics.get(
            "orders"
        )
        ==
        2
    )