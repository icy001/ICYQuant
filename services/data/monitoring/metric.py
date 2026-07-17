"""
Data quality metric.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class QualityMetric:
    name: str
    value: float
    status: str