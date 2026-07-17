"""
Strategy performance score.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyScore:
    strategy_id: str
    sharpe: float
    volatility: float
    drawdown: float