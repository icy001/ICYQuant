from dataclasses import dataclass, field
from typing import List, Optional

from research.portfolio.portfolio import Portfolio
from research.execution.order import Order
from research.data.snapshot import MarketSnapshot


@dataclass
class RiskContext:
    portfolio: Portfolio
    pending_orders: List[Order] = field(default_factory=list)
    market_snapshot: Optional[MarketSnapshot] = None
    account_equity: float = 0.0
    daily_pnl: float = 0.0