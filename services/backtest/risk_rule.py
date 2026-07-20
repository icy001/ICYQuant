"""
Backtest risk rule.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskRule:
    max_position: float
    max_drawdown: float
    max_exposure: float