"""Gauge metric (Commit 27 Part 1.2, spec sections 7-8).

表示当前状态，可以双向移动：

    42 -> 35 -> 51
"""

from __future__ import annotations

from .metric import MetricDefinition


class Gauge:

    def __init__(
        self,
        definition: MetricDefinition,
    ) -> None:

        self.definition = definition

        self._value = 0.0

    @property
    def value(self) -> float:

        return self._value

    def set(
        self,
        value: float,
    ) -> None:

        self._value = value

    def increment(
        self,
        amount: float = 1.0,
    ) -> None:

        self._value += amount

    def decrement(
        self,
        amount: float = 1.0,
    ) -> None:

        self._value -= amount
