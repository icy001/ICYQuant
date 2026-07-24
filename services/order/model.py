from dataclasses import dataclass


@dataclass
class Order:

    order_id: str

    account_id: str

    portfolio_id: str

    symbol: str

    quantity: float

    price: float

    side: str

    order_type: str

    status: str = "CREATED"