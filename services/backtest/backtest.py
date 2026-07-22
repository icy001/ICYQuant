"""
Backtest domain model.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Backtest:

    backtest_id: str

    strategy_id: str

    started_at: datetime

    ended_at: Optional[datetime]