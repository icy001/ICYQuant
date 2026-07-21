"""
Portfolio version models.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PortfolioVersion:
    version_id: str
    portfolio_id: str
    created_at: datetime
    snapshot: dict