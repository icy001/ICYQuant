"""
Projection model.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PortfolioProjection:

    projection_id: str

    portfolio_id: str

    created_at: datetime

    data: dict