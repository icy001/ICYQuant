from dataclasses import dataclass


@dataclass
class PortfolioSnapshot:

    portfolio_id: str

    total_value: float

    timestamp: int