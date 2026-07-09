from dataclasses import dataclass, field
from typing import Dict


@dataclass
class RiskLimits:
    max_position_size: float = 1000.0
    max_order_quantity: float = 500.0
    max_daily_trades: int = 100
    max_exposure: float = 0.5
    max_drawdown: float = 0.03
    min_cash_balance: float = 1000.0
    position_limits: Dict[str, float] = field(default_factory=lambda: {"NVDA": 1000, "GC": 20})
