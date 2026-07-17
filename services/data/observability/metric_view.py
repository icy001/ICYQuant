"""
Metric visualization model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricView:
    name: str
    value: float