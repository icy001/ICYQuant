from dataclasses import dataclass


@dataclass
class Allocation:

    portfolio_id: str

    symbol: str

    weight: float