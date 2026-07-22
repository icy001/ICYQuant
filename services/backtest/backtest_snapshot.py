"""
Backtest snapshot model.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class BacktestSnapshot:

    snapshot_id: str

    workflow_id: str

    created_at: datetime

    state: dict