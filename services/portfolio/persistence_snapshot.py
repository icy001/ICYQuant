"""
Portfolio snapshot models.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PortfolioSnapshotRecord:
    snapshot_id: str
    portfolio_id: str
    created_at: datetime
    data: dict