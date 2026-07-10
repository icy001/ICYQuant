"""
Gauge metric.

Used for current state values.
"""

from __future__ import annotations


class Gauge:
    def __init__(
        self,
        name: str,
    ):
        self.name = name
        self.value = 0

    def set(
        self,
        value,
    ):
        self.value = value

    def get(
        self,
    ):
        return self.value