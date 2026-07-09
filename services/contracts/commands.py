from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CreateOrderCommand(BaseModel):
    user_id: str
    symbol: str
    side: str
    quantity: float
    price: Optional[float] = None
    order_type: str = "MARKET"


class CancelOrderCommand(BaseModel):
    order_id: str
    user_id: str


class ExecuteOrderCommand(BaseModel):
    order_id: str
    user_id: str


class CheckRiskCommand(BaseModel):
    order_id: str
    user_id: str
    quantity: float
