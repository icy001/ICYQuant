"""
Trade domain events.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID


@dataclass(frozen=True)
class TradeCreated:
    trade_id: UUID
    order_id: UUID
    occurred_at: datetime = datetime.now(timezone.utc)