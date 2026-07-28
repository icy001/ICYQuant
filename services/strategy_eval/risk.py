from dataclasses import dataclass


@dataclass
class RiskMetrics:

    volatility: float

    max_drawdown: float

    sharpe: float
