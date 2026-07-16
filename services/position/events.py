"""
Position domain events.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4


@dataclass(frozen=True)
class PositionUpdated:
    event_id: str
    account_id: str
    symbol: str
    quantity: str
    version: int
    occurred_at: datetime


def create_position_updated(
    *,
    account_id: str,
    symbol: str,
    quantity: str,
    version: int,
) -> PositionUpdated:
    return PositionUpdated(
        event_id=str(uuid4()),
        account_id=account_id,
        symbol=symbol,
        quantity=quantity,
        version=version,
        occurred_at=datetime.now(
            timezone.utc
        ),
    )