from dataclasses import dataclass


@dataclass
class RiskLimits:
    max_position_size: float = 1000.0
    max_order_quantity: float = 500.0
    max_daily_trades: int = 100
    max_exposure: float = 0.5
    min_cash_balance: float = 1000.0
