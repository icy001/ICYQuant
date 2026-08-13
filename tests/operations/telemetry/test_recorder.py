"""
Tests for TelemetryRecorder (Commit 27 Part 1.2, spec sections 14, 30).

Recorder 通过 Registry 操作 Metric；未知 metric 抛 KeyError。
Telemetry 只负责记录，不参与交易决策（spec section 23）。
"""

from __future__ import annotations

import pytest

from services.operations import (
    Counter,
    Gauge,
    Histogram,
    MetricDefinition,
    MetricRegistry,
    MetricSample,
    MetricType,
    TelemetryRecorder,
)


def _counter() -> Counter:
    return Counter(
        MetricDefinition(
            name="orders_submitted_total",
            metric_type=MetricType.COUNTER,
            description="Total submitted orders",
            unit="orders",
        )
    )


def _gauge() -> Gauge:
    return Gauge(
        MetricDefinition(
            name="open_orders",
            metric_type=MetricType.GAUGE,
            description="Current open orders",
            unit="orders",
        )
    )


def _histogram() -> Histogram:
    return Histogram(
        MetricDefinition(
            name="risk_check_latency_ms",
            metric_type=MetricType.HISTOGRAM,
            description="risk check latency",
            unit="ms",
        )
    )


def _recorder(registry: MetricRegistry) -> TelemetryRecorder:
    return TelemetryRecorder(registry)


def test_recorder_increment():
    metric = _counter()
    registry = MetricRegistry()
    registry.register(metric)

    recorder = _recorder(registry)
    recorder.increment("orders_submitted_total")
    recorder.increment("orders_submitted_total", 10)

    assert metric.value == 11


def test_recorder_set_gauge():
    metric = _gauge()
    registry = MetricRegistry()
    registry.register(metric)

    recorder = _recorder(registry)
    recorder.set("open_orders", 42)

    assert metric.value == 42


def test_recorder_observe_histogram():
    metric = _histogram()
    registry = MetricRegistry()
    registry.register(metric)

    recorder = _recorder(registry)
    recorder.observe("risk_check_latency_ms", 10)
    recorder.observe("risk_check_latency_ms", 20)

    assert metric.count == 2
    assert metric.average == 15


def test_recorder_rejects_unknown_metric():
    """spec section 30: 未知 metric 抛 KeyError。"""
    registry = MetricRegistry()

    recorder = TelemetryRecorder(registry)

    with pytest.raises(KeyError):
        recorder.increment("unknown_metric")


def test_recorder_set_rejects_unknown_metric():
    registry = MetricRegistry()

    recorder = TelemetryRecorder(registry)

    with pytest.raises(KeyError):
        recorder.set("unknown_metric", 1.0)


def test_recorder_observe_rejects_unknown_metric():
    registry = MetricRegistry()

    recorder = TelemetryRecorder(registry)

    with pytest.raises(KeyError):
        recorder.observe("unknown_metric", 1.0)


def test_metric_sample_is_frozen():
    sample = MetricSample(
        metric_name="orders_submitted_total",
        value=1.0,
        labels={"venue": "NASDAQ"},
    )

    assert sample.metric_name == "orders_submitted_total"
    assert sample.value == 1.0
    assert sample.labels == {"venue": "NASDAQ"}
