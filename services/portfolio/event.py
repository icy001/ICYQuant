"""
Event sourcing event model.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PortfolioEvent:

    event_id: str

    event_type: str

    portfolio_id: str

    occurred_at: datetime

    payload: dict