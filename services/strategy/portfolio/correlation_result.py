"""
Correlation risk result.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CorrelationRiskResult:
    approved: bool
    portfolio_heat: float
    reason: str