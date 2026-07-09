from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class LedgerType(str, Enum):
    CASH = "CASH"
    POSITION = "POSITION"
    TRADE = "TRADE"
    FEE = "FEE"


class LedgerDirection(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class LedgerEntry(BaseModel):
    entry_id: str
    user_id: str
    event_type: str
    symbol: Optional[str] = None
    quantity: Optional[float] = None
    price: Optional[float] = None
    cash_change: float = 0.0
    ledger_type: LedgerType
    direction: LedgerDirection
    amount: float
    reference_id: str
    timestamp: datetime