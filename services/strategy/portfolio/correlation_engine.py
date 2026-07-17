"""
Correlation risk engine.
"""

from __future__ import annotations

from .correlation_result import CorrelationRiskResult


class CorrelationRiskEngine:
    def check(
        self,
        correlation,
        threshold,
    ):
        if correlation > threshold:
            return CorrelationRiskResult(
                approved=False,
                portfolio_heat=correlation,
                reason="HIGH_CORRELATION",
            )

        return CorrelationRiskResult(
            approved=True,
            portfolio_heat=correlation,
            reason="APPROVED",
        )