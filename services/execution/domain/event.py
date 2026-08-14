from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ExecutionEventType(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    PARTIAL_FILL = "PARTIAL_FILL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class ExecutionEvent:
    event_id: str

    execution_request_id: str
    order_id: str

    event_type: ExecutionEventType

    timestamp: datetime

    external_order_id: str | None = None

    execution_id: str | None = None

    filled_quantity: float = 0.0

    fill_price: float | None = None

    cumulative_filled_quantity: float = 0.0

    remaining_quantity: float | None = None

    message: str | None = None

    venue_id: str | None = None

    sequence: int = 0
