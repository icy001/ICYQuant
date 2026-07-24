from dataclasses import dataclass


@dataclass
class Position:

    position_id: str

    account_id: str

    portfolio_id: str

    symbol: str

    quantity: float

    avg_price: float

    side: str

    status: str = "OPEN"