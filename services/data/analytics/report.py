"""
Factor research report.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FactorResearchReport:
    factor: str
    ic: float
    health_score: float