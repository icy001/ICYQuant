"""
Portfolio report models.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PortfolioReport:
    report_id: str
    report_type: str
    created_at: datetime
    content: dict