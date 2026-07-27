from dataclasses import dataclass


@dataclass
class Trade:
    trade_id: str
    order_id: str
    account_id: str
    symbol: str
    quantity: float
    price: float
    side: str
    timestamp: int