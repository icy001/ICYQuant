"""
Enterprise risk report model.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RiskReport:

    report_id: str

    report_type: str

    created_at: datetime

    content: dict