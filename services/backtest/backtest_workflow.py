"""
Institutional backtest workflow.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class BacktestWorkflow:

    workflow_id: str

    experiment_id: str

    strategy_id: str

    created_at: datetime

    state: str