"""
Target weight drift detection.
"""

from __future__ import annotations

from decimal import Decimal


class DriftDetector:
    def calculate(
        self,
        current_weight: Decimal,
        target_weight: Decimal,
    ) -> Decimal:
        return target_weight - current_weight

    def should_rebalance(
        self,
        drift: Decimal,
        threshold: Decimal,
    ) -> bool:
        return abs(drift) > threshold