from dataclasses import dataclass


@dataclass
class Performance:
    strategy_id: str
    return_rate: float
    sharpe_ratio: float
    max_drawdown: float