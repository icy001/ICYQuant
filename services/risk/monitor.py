from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class RiskMetrics:
    drawdown: float = 0.0
    exposure: float = 0.0
    daily_pnl: float = 0.0
    max_position: float = 0.0
    open_orders: int = 0


class RiskMonitor:
    def __init__(self, limits):
        self.limits = limits
        self.metrics = RiskMetrics()
        self.max_equity = 0.0
        self.starting_equity = 0.0

    def update(self, account: Dict, portfolio) -> None:
        equity = account.get("cash", 0) + portfolio.get_total_position_value()

        if self.starting_equity == 0:
            self.starting_equity = equity

        if equity > self.max_equity:
            self.max_equity = equity

        self.metrics.drawdown = (self.max_equity - equity) / self.max_equity if self.max_equity > 0 else 0
        self.metrics.exposure = portfolio.get_exposure()
        self.metrics.max_position = max(portfolio.positions.values(), default=0)
        self.metrics.open_orders = account.get("open_orders", 0)

    def allow_trade(self, account: Dict = None) -> bool:
        if self.metrics.drawdown > self.limits.max_drawdown:
            return False

        if self.metrics.exposure > self.limits.max_exposure:
            return False

        return True

    def check_initial(self, account: Dict) -> bool:
        return self.allow_trade(account)