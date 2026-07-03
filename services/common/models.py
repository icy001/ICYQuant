from datetime import datetime

from pydantic import BaseModel, Field


class Order(BaseModel):
    order_id: str
    user_id: str
    symbol: str
    side: str
    quantity: float
    price: float | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Trade(BaseModel):
    trade_id: str
    user_id: str
    symbol: str
    price: float
    quantity: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
