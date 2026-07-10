from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioSignal:
    symbol: str
    target_weight: float