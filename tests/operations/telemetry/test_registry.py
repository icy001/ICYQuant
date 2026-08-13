"""
Tests for MetricRegistry (Commit 27 Part 1.2, spec sections 10-11, 29).

Registry 让指标名成为稳定系统契约，避免 Metrics Schema 混乱。
"""

from __future__ import annotations

import pytest

from services.operations import (
    Counter,
    Gauge,
    Histogram,
    MetricDefinition,
    MetricRegistry,
    MetricType,
)


def _counter(name: str) -> Counter:
    return Counter(
        MetricDefinition(
            name=name,
            metric_type=MetricType.COUNTER,
            description=name,
        )
    )


def test_registry_register_and_get():
    registry = MetricRegistry()
    metric = _counter("orders_submitted_total")

    registry.register(metric)

    assert registry.get("orders_submitted_total") is metric


def test_registry_rejects_duplicate_metric():
    """spec section 29: 重复注册抛 ValueError。"""
    registry = MetricRegistry()
    definition = MetricDefinition(
        name="orders_total",
        metric_type=MetricType.COUNTER,
        description="orders",
    )

    registry.register(Counter(definition))

    with pytest.raises(ValueError):
        registry.register(Counter(definition))


def test_registry_get_unknown_returns_none():
    registry = MetricRegistry()

    assert registry.get("missing") is None


def test_registry_contains_registered_metric():
    registry = MetricRegistry()
    registry.register(_counter("orders_total"))

    assert registry.contains("orders_total")
    assert not registry.contains("missing")


def test_registry_all_returns_registered_metrics():
    registry = MetricRegistry()
    registry.register(_counter("orders_total"))
    registry.register(
        Gauge(
            MetricDefinition(
                name="open_orders",
                metric_type=MetricType.GAUGE,
                description="open orders",
            )
        )
    )

    metrics = registry.all()

    assert len(metrics) == 2
    assert {m.definition.name for m in metrics} == {
        "orders_total",
        "open_orders",
    }


def test_registry_supports_histogram():
    registry = MetricRegistry()
    metric = Histogram(
        MetricDefinition(
            name="risk_check_latency_ms",
            metric_type=MetricType.HISTOGRAM,
            description="risk check latency",
            unit="ms",
        )
    )

    registry.register(metric)

    assert registry.contains("risk_check_latency_ms")
