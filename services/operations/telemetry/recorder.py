"""Telemetry recorder (Commit 27 Part 1.2, spec sections 14, 23).

Telemetry 只负责记录，不参与交易决策（spec section 23）：

    Telemetry -> Metric -> Alert -> Incident -> Control Plane -> Pause / Kill / Failover

错误：if latency > 500: reject_order()
Operations 和 Control 始终保持边界。
"""

from __future__ import annotations

from dataclasses import dataclass

from .registry import MetricRegistry


@dataclass(frozen=True)
class MetricSample:

    metric_name: str

    value: float

    labels: dict[str, str]


class TelemetryRecorder:

    def __init__(
        self,
        registry: MetricRegistry,
    ) -> None:

        self.registry = registry

    def increment(
        self,
        metric_name: str,
        amount: float = 1.0,
    ) -> None:

        metric = self.registry.get(
            metric_name
        )

        if metric is None:
            raise KeyError(metric_name)

        metric.increment(amount)

    def set(
        self,
        metric_name: str,
        value: float,
    ) -> None:

        metric = self.registry.get(
            metric_name
        )

        if metric is None:
            raise KeyError(metric_name)

        metric.set(value)

    def observe(
        self,
        metric_name: str,
        value: float,
    ) -> None:

        metric = self.registry.get(
            metric_name
        )

        if metric is None:
            raise KeyError(metric_name)

        metric.observe(value)
