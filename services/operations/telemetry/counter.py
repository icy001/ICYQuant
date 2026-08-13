"""Counter metric (Commit 27 Part 1.2, spec sections 5-6).

只增不减：

    orders_submitted_total = 125,421

increment(amount) 必须非负，否则抛 ValueError（spec section 26）。
"""

from __future__ import annotations

from .metric import MetricDefinition


class Counter:

    def __init__(
        self,
        definition: MetricDefinition,
    ) -> None:

        self.definition = definition

        self._value = 0.0

    @property
    def value(self) -> float:

        return self._value

    def increment(
        self,
        amount: float = 1.0,
    ) -> None:

        if amount < 0:
            raise ValueError(
                "counter increment must be non-negative"
            )

        self._value += amount

    def reset(self) -> None:

        self._value = 0.0
