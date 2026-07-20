"""
Backtest lifecycle.
"""

from enum import Enum


class BacktestStatus(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"