"""
Backtest execution context.
"""

from dataclasses import dataclass

from .configuration import BacktestConfiguration


@dataclass(frozen=True)
class BacktestContext:
    dataset: str
    configuration: BacktestConfiguration