from dataclasses import dataclass


@dataclass
class BacktestJob:
    job_id: str
    strategy_id: str
    symbol: str
    start_date: str
    end_date: str