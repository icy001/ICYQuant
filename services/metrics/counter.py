"""
Counter metric.

Used for cumulative events.
"""

from __future__ import annotations


class Counter:
    def __init__(
        self,
        name: str,
    ):
        self.name = name
        self.value = 0

    def inc(
        self,
        amount: int = 1,
    ):
        self.value += amount

    def get(
        self,
    ) -> int:
        return self.value