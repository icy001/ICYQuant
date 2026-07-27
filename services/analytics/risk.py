from dataclasses import dataclass


@dataclass
class RiskMetric:
    volatility: float
    beta: float
    sharpe: float