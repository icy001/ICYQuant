from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from services.contracts.dto import CashBalanceDTO, OrderDTO, PositionDTO, TradeDTO


class Snapshot(BaseModel):
    snapshot_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    positions: List[PositionDTO] = Field(default_factory=list)
    cash_balances: List[CashBalanceDTO] = Field(default_factory=list)
    trades: List[TradeDTO] = Field(default_factory=list)
    orders: List[OrderDTO] = Field(default_factory=list)
    metadata: Dict[str, str] = Field(default_factory=dict)
