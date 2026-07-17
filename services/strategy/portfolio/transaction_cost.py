"""
Transaction cost estimator.
"""

from __future__ import annotations

from decimal import Decimal


class TransactionCostEstimator:
    def estimate(
        self,
        trade_value: Decimal,
        rate: Decimal,
    ) -> Decimal:
        return trade_value * rate