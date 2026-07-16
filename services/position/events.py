"""
Position domain events.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class PositionUpdated:
    account_id: str
    symbol: str
    quantity: str
    occurred_at: datetime = datetime.now(timezone.utc)