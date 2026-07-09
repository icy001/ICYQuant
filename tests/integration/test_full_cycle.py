import pytest

from services.execution.adapters.paper import PaperAdapter
from services.execution.gateway import ExecutionGateway
from services.oms.models import Order
from services.oms.service import OMSService
from services.portfolio.portfolio import Portfolio
from services.risk.dashboard import RiskDashboard
from services.risk.limits import RiskLimits
from services.risk.monitor import RiskMonitor
from services.trading.safety_guard import LiveSafetyGuard
from services.trading.session import TradingSession
from services.trading.mode import TradingMode


class TestFullCycle:
    def test_trading_session_start(self):
        gateway = ExecutionGateway()
        limits = RiskLimits()
        monitor = RiskMonitor(limits)
        portfolio = Portfolio(cash=100000.0)

        session = TradingSession(gateway, monitor, portfolio)

        assert session.start() is True
        assert session.is_ready() is True

    def test_trading_session_stop(self):
        gateway = ExecutionGateway()
        limits = RiskLimits()
        monitor = RiskMonitor(limits)
        portfolio = Portfolio(cash=100000.0)

        session = TradingSession(gateway, monitor, portfolio)
        session.start()

        assert session.stop() is True

    def test_live_safety_guard(self):
        gateway = ExecutionGateway()
        gateway.connect(TradingMode.PAPER.value)

        limits = RiskLimits()
        monitor = RiskMonitor(limits)
        portfolio = Portfolio(cash=100000.0)

        guard = LiveSafetyGuard(gateway, monitor, portfolio)
        report = guard.perform_checks()

        assert report.allowed is True
        assert all(check.passed for check in report.checks)

    def test_risk_dashboard_update(self):
        limits = RiskLimits()
        monitor = RiskMonitor(limits)
        dashboard = RiskDashboard()

        portfolio = Portfolio(cash=100000.0)
        account = {"cash": 100000.0}

        monitor.update(account, portfolio)
        dashboard.update(monitor)

        assert dashboard.status == "OK"
        assert len(dashboard.violations) == 0

    def test_full_trade_with_safety_guard(self):
        gateway = ExecutionGateway()
        limits = RiskLimits()
        monitor = RiskMonitor(limits)
        portfolio = Portfolio(cash=100000.0)

        session = TradingSession(gateway, monitor, portfolio)
        session.start()

        guard = LiveSafetyGuard(gateway, monitor, portfolio)
        report = guard.perform_checks()

        assert report.allowed is True

        order_service = OMSService()
        order = order_service.create_order("NVDA", "BUY", 100, 480.0)

        fill = gateway.send_order(order, TradingMode.PAPER.value)
        assert fill is not None

        delta = fill.quantity if order.side == "BUY" else -fill.quantity
        portfolio.update_position(fill.symbol, delta)
        portfolio.cash -= fill.quantity * fill.price

        assert portfolio.positions["NVDA"] == 100

        session.stop()