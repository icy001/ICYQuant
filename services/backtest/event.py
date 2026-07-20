"""
Backtest event model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BacktestEvent:
    event_type: str
    timestamp: str
    payload: dict