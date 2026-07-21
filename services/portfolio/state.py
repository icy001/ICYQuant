"""
Portfolio state.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class PortfolioStatus(Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    SUSPENDED = "SUSPENDED"


@dataclass(frozen=True)
class PortfolioState:

    state_id: str

    portfolio_id: str

    version: int

    updated_at: datetime

    data: dict