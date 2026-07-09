from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class LedgerType(str, Enum):
    CASH = "CASH"
    POSITION = "POSITION"


class LedgerDirection(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class LedgerEntry(BaseModel):
    entry_id: str
    user_id: str
    symbol: Optional[str] = None
    ledger_type: LedgerType
    direction: LedgerDirection
    amount: float
    reference_id: str
    timestamp: datetime
