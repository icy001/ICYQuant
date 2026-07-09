from datetime import datetime

from .lifecycle import SessionStatus, TradingLifecycle
from .mode import TradingMode, get_trading_mode


class TradingSession:
    def __init__(self, gateway, risk_monitor, portfolio):
        self.gateway = gateway
        self.risk_monitor = risk_monitor
        self.portfolio = portfolio
        self.lifecycle = TradingLifecycle()
        self.mode = get_trading_mode()
        self.start_time = None
        self.account_info = None

    def start(self) -> bool:
        if not self.lifecycle.transition(SessionStatus.CONNECT):
            return False

        if not self.gateway.connect():
            return False

        self.account_info = self.gateway.get_account()
        if not self.account_info:
            return False

        if not self._sync_positions():
            return False

        if not self.lifecycle.transition(SessionStatus.READY):
            return False

        if not self.risk_monitor.check_initial(self.account_info):
            return False

        if self.mode == TradingMode.LIVE:
            if not self._safety_check():
                return False

        self.start_time = datetime.utcnow()
        return self.lifecycle.transition(SessionStatus.TRADING)

    def stop(self) -> bool:
        self.gateway.disconnect()
        return self.lifecycle.transition(SessionStatus.STOP)

    def is_ready(self) -> bool:
        return self.lifecycle.status == SessionStatus.TRADING

    def _sync_positions(self) -> bool:
        try:
            positions = self.gateway.get_positions()
            for symbol, quantity in positions.items():
                self.portfolio.set_position(symbol, quantity)
            return True
        except Exception:
            return False

    def _safety_check(self) -> bool:
        checks = [
            self._check_account(),
            self._check_risk(),
            self._check_position_sync(),
            self._check_reconciliation(),
        ]
        return all(checks)

    def _check_account(self) -> bool:
        return self.account_info is not None

    def _check_risk(self) -> bool:
        return self.risk_monitor.allow_trade(self.account_info)

    def _check_position_sync(self) -> bool:
        gateway_positions = self.gateway.get_positions()
        portfolio_positions = self.portfolio.positions
        return gateway_positions == portfolio_positions

    def _check_reconciliation(self) -> bool:
        return True