"""
Tests for Gauge metric (Commit 27 Part 1.2, spec sections 7-8, 27).

Gauge 表示当前状态，可以双向移动：42 -> 35 -> 51
"""

from __future__ import annotations

from services.operations import (
    Gauge,
    MetricDefinition,
    MetricType,
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


def test_gauge_can_move_both_directions():
    """spec section 27: set(100) + decrement(25) == 75。"""
    metric = _gauge()

    metric.set(100)
    metric.decrement(25)

    assert metric.value == 75


def test_gauge_set_overwrites_value():
    metric = _gauge()

    metric.set(10)
    metric.set(20)

    assert metric.value == 20


def test_gauge_increment():
    """spec section 8: 42 -> 51。"""
    metric = _gauge()
    metric.set(42)

    metric.increment(9)

    assert metric.value == 51


def test_gauge_decrement():
    """spec section 8: 42 -> 35。"""
    metric = _gauge()
    metric.set(42)

    metric.decrement(7)

    assert metric.value == 35


def test_gauge_starts_at_zero():
    metric = _gauge()

    assert metric.value == 0
