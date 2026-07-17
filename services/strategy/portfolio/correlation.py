"""
Asset correlation calculator.
"""

from __future__ import annotations

from decimal import Decimal


class CorrelationCalculator:
    def calculate(
        self,
        returns_a: list[Decimal],
        returns_b: list[Decimal],
    ) -> Decimal:
        if len(returns_a) != len(returns_b):
            raise ValueError("length mismatch")

        return Decimal("0.0")