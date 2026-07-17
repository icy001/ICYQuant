"""
Risk contribution attribution.
"""

from __future__ import annotations


class RiskAttribution:
    def calculate(
        self,
        positions,
    ):
        result = {}

        for symbol, risk in positions.items():
            result[symbol] = risk

        return result