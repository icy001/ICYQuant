from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional


@dataclass
class RiskMetrics:
    drawdown: float = 0.0
    exposure: float = 0.0
    daily_pnl: float = 0.0
    max_position: float = 0.0
    open_orders: int = 0
    daily_loss: float = 0.0
    trades_today: int = 0


class RiskMonitor:
    def __init__(self, limits):
        self.limits = limits
        self.metrics = RiskMetrics()
        self.max_equity = 0.0
        self.starting_equity = 0.0
        self.daily_start_equity = 0.0
        self.last_trade_date = None
        self.trading_blocked = False

    def update(self, account: Dict, portfolio) -> None:
        self._check_new_day()

        equity = account.get("cash", 0) + portfolio.get_total_position_value()

        if self.starting_equity == 0:
            self.starting_equity = equity
            self.daily_start_equity = equity

        if equity > self.max_equity:
            self.max_equity = equity

        self.metrics.drawdown = (self.max_equity - equity) / self.max_equity if self.max_equity > 0 else 0
        self.metrics.exposure = portfolio.get_exposure()
        self.metrics.max_position = max(portfolio.positions.values(), default=0)
        self.metrics.open_orders = account.get("open_orders", 0)
        self.metrics.daily_pnl = equity - self.daily_start_equity
        self.metrics.daily_loss = max(0, self.daily_start_equity - equity)

        self._check_circuit_breaker()

    def _check_new_day(self) -> None:
        today = datetime.utcnow().date()
        if self.last_trade_date is None:
            self.last_trade_date = today
        elif self.last_trade_date != today:
            self.daily_start_equity = self._get_current_equity()
            self.metrics.trades_today = 0
            self.trading_blocked = False
            self.last_trade_date = today

    def _get_current_equity(self) -> float:
        return 0.0

    def _check_circuit_breaker(self) -> None:
        daily_loss_limit = self.limits.max_drawdown * self.daily_start_equity
        if self.metrics.daily_loss > daily_loss_limit:
            self.trading_blocked = True

    def allow_trade(self, account: Dict = None) -> bool:
        if self.trading_blocked:
            return False

        if self.metrics.drawdown > self.limits.max_drawdown:
            return False

        if self.metrics.exposure > self.limits.max_exposure:
            return False

        if self.metrics.trades_today >= self.limits.max_daily_trades:
            return False

        return True

    def check_initial(self, account: Dict) -> bool:
        return self.allow_trade(account)

    def on_trade(self) -> None:
        self.metrics.trades_today += 1

    def reset_daily(self) -> None:
        self.metrics.daily_pnl = 0.0
        self.metrics.daily_loss = 0.0
        self.metrics.trades_today = 0
        self.trading_blocked = False