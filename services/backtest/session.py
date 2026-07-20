"""
Backtest session model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BacktestSession:
    session_id: str
    strategy_id: str
    status: str