"""
Backtest status.
"""

from enum import Enum


class BacktestStatus(Enum):

    CREATED = "CREATED"

    RUNNING = "RUNNING"

    COMPLETED = "COMPLETED"

    FAILED = "FAILED"