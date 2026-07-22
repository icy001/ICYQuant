"""
Unified risk metric.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskMetric:

    metric: str

    value: float

    source: str