from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventType(str, Enum):
    ORDER_CREATED = "ORDER_CREATED"
    RISK_CHECKED = "RISK_CHECKED"
    ORDER_APPROVED = "ORDER_APPROVED"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORDER_SENT = "ORDER_SENT"
    TRADE_EXECUTED = "TRADE_EXECUTED"
    POSITION_CHANGED = "POSITION_CHANGED"


class Event(BaseModel):
    event_id: str
    event_type: EventType
    order_id: str
    timestamp: datetime
    payload: dict[str, Any] = Field(default_factory=dict)
