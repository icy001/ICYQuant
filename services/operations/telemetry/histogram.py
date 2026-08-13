"""Histogram metric (Commit 27 Part 1.2, spec section 9).

描述分布：

    risk_check_latency_ms
        p50 = 1.2 ms
        p95 = 4.8 ms
        p99 = 12.1 ms

第一版保持简单，只记录原始值。后续接入真正的 metrics backend 时再把

    values -> bucket aggregation -> quantile

下沉到 telemetry backend。
"""

from __future__ import annotations

from .metric import MetricDefinition


class Histogram:

    def __init__(
        self,
        definition: MetricDefinition,
        buckets: tuple[float, ...] = (),
    ) -> None:

        self.definition = definition

        self.buckets = buckets

        self._values: list[float] = []

    def observe(
        self,
        value: float,
    ) -> None:

        self._values.append(value)

    @property
    def count(self) -> int:

        return len(self._values)

    @property
    def total(self) -> float:

        return sum(self._values)

    @property
    def average(self) -> float:

        if not self._values:
            return 0.0

        return self.total / self.count

    def values(self) -> tuple[float, ...]:

        return tuple(self._values)
