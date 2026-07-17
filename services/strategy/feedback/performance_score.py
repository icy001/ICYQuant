"""
Strategy performance scoring.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PerformanceScore:
    strategy_id: str
    sharpe: float
    pnl: float
    drawdown: float
    win_rate: float