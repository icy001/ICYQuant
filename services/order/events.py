"""
Order domain events.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID


@dataclass(frozen=True)
class OrderEvent:

    order_id: UUID

    occurred_at: datetime = datetime.now(
        timezone.utc
    )


@dataclass(frozen=True)
class OrderCreated(OrderEvent):
    pass


@dataclass(frozen=True)
class OrderCancelled(OrderEvent):
    pass


@dataclass(frozen=True)
class OrderFilled(OrderEvent):
    pass