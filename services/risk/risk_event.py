"""
Risk event model.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RiskEvent:

    event_id: str

    event_type: str

    level: str

    message: str

    created_at: datetime