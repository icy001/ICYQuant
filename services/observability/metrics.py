"""
ICYQuant metrics collector.

Provides application metrics.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(
)
class Metric:
    __slots__ = (
        "name",
        "value",
    )
    name: str
    value: float


class MetricsCollector:
    def __init__(self):
        self.metrics = {}

    def increment(
        self,
        name: str,
        value: float = 1,
    ):
        current = (
            self.metrics
            .get(
                name,
                0
            )
        )
        self.metrics[name] = (
            current
            +
            value
        )

    def set(
        self,
        name: str,
        value: float,
    ):
        self.metrics[name] = value

    def get(
        self,
        name: str,
    ) -> float:
        return (
            self.metrics
            .get(
                name,
                0
            )
        )

    def snapshot(self):
        return dict(
            self.metrics
        )