"""
Performance metrics.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PerformanceMetrics:
    total_return: float
    annual_return: float
    sharpe_ratio: float