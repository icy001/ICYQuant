"""
Portfolio event record.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PortfolioEvent:

    event_id: str

    portfolio_id: str

    event_type: str

    created_at: datetime

    payload: dict