"""
Order domain events.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID


class OrderTransition(str, Enum):
    SUBMIT = "SUBMIT"
    ACCEPT = "ACCEPT"
    PARTIAL_FILL = "PARTIAL_FILL"
    FILL = "FILL"
    CANCEL = "CANCEL"
    REJECT = "REJECT"
    EXPIRE = "EXPIRE"
    REPLACE = "REPLACE"


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