from dataclasses import dataclass


@dataclass
class BacktestResult:
    job_id: str
    total_return: float
    max_drawdown: float
    trades: int