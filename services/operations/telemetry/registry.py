"""Metric registry (Commit 27 Part 1.2, spec sections 10-11).

避免不同服务随意定义：

    orders_total / order_count / total_orders / submitted_orders

最终导致 Metrics Schema 混乱。统一 Registry 后：

    orders_submitted_total / orders_filled_total / orders_rejected_total

成为稳定的系统契约。
"""

from __future__ import annotations

from typing import Union

from .counter import Counter
from .gauge import Gauge
from .histogram import Histogram

Metric = Union[Counter, Gauge, Histogram]


class MetricRegistry:

    def __init__(self) -> None:

        self._metrics: dict[str, Metric] = {}

    def register(
        self,
        metric: Metric,
    ) -> None:

        name = metric.definition.name

        if name in self._metrics:
            raise ValueError(
                f"metric already registered: {name}"
            )

        self._metrics[name] = metric

    def get(
        self,
        name: str,
    ) -> Metric | None:

        return self._metrics.get(name)

    def all(self) -> tuple[Metric, ...]:

        return tuple(
            self._metrics.values()
        )

    def contains(
        self,
        name: str,
    ) -> bool:

        return name in self._metrics
