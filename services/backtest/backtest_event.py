"""
Backtest event model.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class BacktestEvent:

    event_id: str

    event_type: str

    timestamp: datetime

    payload: dict