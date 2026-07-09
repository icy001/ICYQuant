import pytest

from services.portfolio.portfolio import Portfolio
from services.risk.limits import RiskLimits
from services.risk.monitor import RiskMonitor


class TestDrawdown:
    def test_risk_monitor_initial(self):
        limits = RiskLimits(max_drawdown=0.03)
        monitor = RiskMonitor(limits)

        account = {"cash": 100000.0}
        portfolio = Portfolio(cash=100000.0)

        monitor.update(account, portfolio)

        assert monitor.metrics.drawdown == 0.0
        assert monitor.allow_trade(account) is True

    def test_risk_monitor_drawdown_within_limit(self):
        limits = RiskLimits(max_drawdown=0.03)
        monitor = RiskMonitor(limits)

        account = {"cash": 100000.0}
        portfolio = Portfolio(cash=100000.0)
        monitor.update(account, portfolio)

        account = {"cash": 98000.0}
        portfolio = Portfolio(cash=98000.0)
        monitor.update(account, portfolio)

        assert monitor.metrics.drawdown == 0.02
        assert monitor.allow_trade(account) is True

    def test_risk_monitor_drawdown_exceeds_limit(self):
        limits = RiskLimits(max_drawdown=0.03)
        monitor = RiskMonitor(limits)

        account = {"cash": 100000.0}
        portfolio = Portfolio(cash=100000.0)
        monitor.update(account, portfolio)

        account = {"cash": 96000.0}
        portfolio = Portfolio(cash=96000.0)
        monitor.update(account, portfolio)

        assert monitor.metrics.drawdown == 0.04
        assert monitor.allow_trade(account) is False

    def test_risk_monitor_exposure(self):
        limits = RiskLimits(max_exposure=0.5)
        monitor = RiskMonitor(limits)

        portfolio = Portfolio(cash=100000.0)
        portfolio.market_prices["NVDA"] = 480.0
        portfolio.positions["NVDA"] = 100

        account = {"cash": 100000.0}
        monitor.update(account, portfolio)

        expected_exposure = (100 * 480) / (100000 + 100 * 480)
        assert monitor.metrics.exposure == pytest.approx(expected_exposure)
        assert monitor.allow_trade(account) is True