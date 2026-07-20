"""
Backtest session.
"""

from dataclasses import dataclass


@dataclass
class BacktestSession:
    session_id: str
    experiment_id: str
    status: str = "CREATED"