"""
Backtest experiment model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BacktestExperiment:
    experiment_id: str
    strategy_id: str
    version: str