"""
Backtest execution context.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class BacktestContext:

    strategy_id: str

    symbol: str

    start_time: datetime

    end_time: datetime

    initial_cash: float