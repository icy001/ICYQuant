"""
Performance metrics model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PerformanceMetrics:

    total_return: float

    annual_return: float

    max_drawdown: float

    sharpe_ratio: float

    sortino_ratio: float