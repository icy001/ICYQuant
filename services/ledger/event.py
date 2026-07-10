from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Optional
from uuid import UUID, uuid4


class LedgerEventType(Enum):
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    ORDER_CREATED = "ORDER_CREATED"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_PARTIALLY_FILLED = "ORDER_PARTIALLY_FILLED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    ORDER_REJECTED = "ORDER_REJECTED"
    COMMISSION_CHARGED = "COMMISSION_CHARGED"
    DIVIDEND_RECEIVED = "DIVIDEND_RECEIVED"
    CASH_ADJUSTED = "CASH_ADJUSTED"
    MARKET_PRICE_UPDATED = "MARKET_PRICE_UPDATED"
    POSITION_OPENED = "POSITION_OPENED"
    POSITION_CLOSED = "POSITION_CLOSED"


@dataclass
class LedgerEvent:
    event_type: LedgerEventType
    event_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.utcnow())
    payload: Dict = field(default_factory=dict)
    stream_id: str = "default"