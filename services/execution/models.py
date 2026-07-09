from dataclasses import dataclass


@dataclass
class Fill:
    order_id: str
    symbol: str
    quantity: float
    price: float