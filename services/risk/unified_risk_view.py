"""
Unified risk view.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class UnifiedRiskView:

    metrics: dict

    risk_score: float