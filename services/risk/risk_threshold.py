"""
Risk threshold configuration.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskThreshold:

    metric: str

    warning: float

    critical: float