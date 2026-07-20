"""
Backtest configuration.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BacktestConfiguration:
    initial_cash: float
    commission: float
    slippage: float