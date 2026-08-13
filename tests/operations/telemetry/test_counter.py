"""
Tests for Counter metric (Commit 27 Part 1.2, spec sections 5-6, 25-26).

Counter 只增不减；increment(amount) 必须非负，否则抛 ValueError。
"""

from __future__ import annotations

import pytest

from services.operations import (
    Counter,
    MetricDefinition,
    MetricType,
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


def test_counter_increment():
    """spec section 25: increment() 后 value == 1。"""
    metric = _counter()

    metric.increment()

    assert metric.value == 1


def test_counter_increment_by_amount():
    metric = _counter()

    metric.increment(10)

    assert metric.value == 10


def test_counter_increments_accumulate():
    """spec section 6: increment() + increment(10) == 11。"""
    metric = _counter()

    metric.increment()
    metric.increment(10)

    assert metric.value == 11


def test_counter_rejects_negative_increment():
    """spec section 26: 负数 increment 抛 ValueError。"""
    metric = _counter()

    with pytest.raises(ValueError):
        metric.increment(-1)


def test_counter_starts_at_zero():
    metric = _counter()

    assert metric.value == 0


def test_counter_reset():
    metric = _counter()
    metric.increment(5)

    metric.reset()

    assert metric.value == 0
