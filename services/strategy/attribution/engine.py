"""
Portfolio attribution engine.
"""

from __future__ import annotations

from .attribution_result import AttributionResult


class AttributionEngine:
    def __init__(
        self,
        strategy,
        factor,
        risk,
    ):
        self.strategy = strategy
        self.factor = factor
        self.risk = risk

    def analyze(
        self,
        trades,
        exposure,
        positions,
    ):
        return AttributionResult(
            pnl_by_strategy=self.strategy.calculate(trades),
            pnl_by_factor=self.factor.calculate(exposure, {}),
            risk_by_asset=self.risk.calculate(positions),
        )