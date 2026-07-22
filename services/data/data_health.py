"""
Market data health model.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DataHealth:

    component: str

    status: str

    checked_at: datetime

    message: str