from dataclasses import dataclass


@dataclass
class OptimizationResult:
    portfolio_id: str
    weights: list
    expected_return: float
    risk: float