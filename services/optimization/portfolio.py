from dataclasses import dataclass


@dataclass
class Portfolio:
    portfolio_id: str
    name: str
    capital: float