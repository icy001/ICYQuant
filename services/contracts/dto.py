from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class OrderDTO(BaseModel):
    order_id: str
    user_id: str
    symbol: str
    side: str
    quantity: float
    price: Optional[float] = None
    status: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TradeDTO(BaseModel):
    trade_id: str
    user_id: str
    symbol: str
    price: float
    quantity: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PositionDTO(BaseModel):
    user_id: str
    symbol: str
    quantity: float
    avg_cost: Optional[float] = None


class CashBalanceDTO(BaseModel):
    user_id: str
    balance: float
    currency: str = "USD"
