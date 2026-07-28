from dataclasses import dataclass


@dataclass
class BacktestResult:

    return_rate: float

    sharpe: float

    drawdown: float
