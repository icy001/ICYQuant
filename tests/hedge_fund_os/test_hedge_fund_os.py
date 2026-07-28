"""Tests for AI Autonomous Hedge Fund Operating System."""

from services.hedge_fund_os import (
    CapitalManagementEngine,
    ComplianceMonitor,
    Fund,
    FundAccountingInterface,
    FundMemory,
    FundRiskDashboard,
    HedgeFundOSService,
    InvestorReportingEngine,
    NAVEngine,
    PerformanceAttributionEngine,
)


def test_nav():
    engine = NAVEngine()
    result = engine.calculate(10_000_000, 1_000_000)
    assert result == 9_000_000


def test_nav_zero():
    engine = NAVEngine()
    assert engine.calculate(1_000_000, 1_000_000) == 0


def test_nav_negative():
    engine = NAVEngine()
    assert engine.calculate(500_000, 1_000_000) == -500_000


def test_fund_entity():
    fund = Fund(id="f1", name="ICY Alpha Fund", strategy="long_short")
    assert fund.id == "f1"
    assert fund.name == "ICY Alpha Fund"
    assert fund.strategy == "long_short"


def test_capital_management():
    engine = CapitalManagementEngine()
    result = engine.allocate(100_000_000, {"equity": 0.6, "bond": 0.4})
    assert result["capital"] == 100_000_000
    assert result["allocation"] == {"equity": 0.6, "bond": 0.4}


def test_fund_risk_dashboard():
    dashboard = FundRiskDashboard()
    result = dashboard.analyze({"exposure": 0.8})
    assert result["drawdown"] == 0
    assert result["risk"] == "normal"


def test_performance_attribution():
    engine = PerformanceAttributionEngine()
    result = engine.analyze(0.15)
    assert result["alpha"] == 0.15


def test_fund_accounting():
    interface = FundAccountingInterface()
    trades = [{"id": "t1", "symbol": "NVDA", "qty": 100}]
    result = interface.reconcile(trades)
    assert result["status"] == "matched"


def test_investor_reporting():
    engine = InvestorReportingEngine()
    data = {"nav": 10_000_000, "return": 0.15, "drawdown": 0.05}
    result = engine.generate(data)
    assert result["report"] == data


def test_compliance_monitor():
    monitor = ComplianceMonitor()
    assert monitor.check({"exposure": 0.8}) is True


def test_fund_memory():
    memory = FundMemory()
    memory.save({"event": "nav_calculated", "nav": 10_000_000})
    memory.save({"event": "risk_event", "type": "drawdown"})
    assert len(memory.history) == 2
    assert memory.history[0]["nav"] == 10_000_000


def test_hedge_fund_os_service():
    nav_engine = NAVEngine()
    service = HedgeFundOSService(nav_engine)
    result = service.nav(50_000_000, 5_000_000)
    assert result == 45_000_000


def test_full_fund_operations_workflow():
    """End-to-end: fund setup → NAV → risk → attribution → reporting → memory."""
    # 1. Create fund entity
    fund = Fund(id="f1", name="ICY Alpha Fund", strategy="market_neutral")
    assert fund.strategy == "market_neutral"

    # 2. Calculate NAV
    nav_engine = NAVEngine()
    nav = nav_engine.calculate(100_000_000, 10_000_000)
    assert nav == 90_000_000

    # 3. Capital management
    capital = CapitalManagementEngine()
    alloc = capital.allocate(nav, {"equity": 0.7, "bond": 0.2, "cash": 0.1})
    assert alloc["capital"] == 90_000_000

    # 4. Fund risk dashboard
    dashboard = FundRiskDashboard()
    risk = dashboard.analyze({"exposure": 0.7})
    assert risk["risk"] == "normal"

    # 5. Performance attribution
    attribution = PerformanceAttributionEngine()
    perf = attribution.analyze(0.12)
    assert perf["alpha"] == 0.12

    # 6. Compliance check
    monitor = ComplianceMonitor()
    assert monitor.check({"exposure": 0.7}) is True

    # 7. Generate investor report
    reporter = InvestorReportingEngine()
    report = reporter.generate({"nav": nav, "return": 0.12, "risk": risk})
    assert report["report"]["nav"] == nav

    # 8. Accounting reconciliation
    accounting = FundAccountingInterface()
    recon = accounting.reconcile([{"id": "t1", "symbol": "AAPL", "qty": 500}])
    assert recon["status"] == "matched"

    # 9. Fund memory
    memory = FundMemory()
    memory.save({"nav": nav, "return": 0.12, "risk": "normal"})
    assert len(memory.history) == 1
