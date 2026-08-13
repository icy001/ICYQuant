"""
Tests for Histogram metric (Commit 27 Part 1.2, spec sections 9, 28).

第一版只记录原始值；bucket aggregation / quantile 后续下沉到 backend。
"""

from __future__ import annotations

from services.operations import (
    Histogram,
    MetricDefinition,
    MetricType,
)


def _histogram() -> Histogram:
    return Histogram(
        MetricDefinition(
            name="execution_latency_ms",
            metric_type=MetricType.HISTOGRAM,
            description="execution latency",
            unit="ms",
        )
    )


def test_histogram_observe():
    """spec section 28: observe(10) + observe(20) == count 2, average 15。"""
    metric = _histogram()

    metric.observe(10)
    metric.observe(20)

    assert metric.count == 2
    assert metric.average == 15


def test_histogram_total_sums_observations():
    metric = _histogram()

    metric.observe(1.5)
    metric.observe(2.5)

    assert metric.total == 4.0


def test_histogram_average_empty_is_zero():
    metric = _histogram()

    assert metric.average == 0.0
    assert metric.count == 0
    assert metric.total == 0.0


def test_histogram_values_returns_snapshot():
    metric = _histogram()
    metric.observe(10)
    metric.observe(20)

    assert metric.values() == (10, 20)


def test_histogram_supports_buckets_definition():
    metric = Histogram(
        MetricDefinition(
            name="risk_check_latency_ms",
            metric_type=MetricType.HISTOGRAM,
            description="risk check latency",
            unit="ms",
        ),
        buckets=(1.0, 5.0, 10.0),
    )

    assert metric.buckets == (1.0, 5.0, 10.0)
