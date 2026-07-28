from dataclasses import dataclass


@dataclass
class FactorPerformance:

    factor_id: str

    return_value: float

    volatility: float

    sharpe: float
