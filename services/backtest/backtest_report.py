"""
Backtest report model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BacktestReport:

    summary: dict

    performance: dict

    trades: list