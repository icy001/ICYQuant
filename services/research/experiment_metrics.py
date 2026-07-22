"""
Experiment metrics.
"""

from dataclasses import dataclass


@dataclass
class ExperimentMetrics:

    ic: float

    rank_ic: float

    sharpe: float

    max_drawdown: float

    annual_return: float