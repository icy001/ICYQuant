from decimal import Decimal

from services.portfolio import (
    KPICalculator,
    AnalyticsMetric,
    PortfolioKPI,
    RiskMetric,
    PerformanceMetric,
    PortfolioAnalyticsEngine,
    PortfolioAnalyticsService,
    DashboardSnapshot,
)


def test_return_metric():
    calculator = KPICalculator()

    result = calculator.calculate_return(
        Decimal("100"),
        Decimal("110"),
    )

    assert result == Decimal("0.1")


def test_return_metric_zero_start():
    calculator = KPICalculator()

    result = calculator.calculate_return(
        Decimal("0"),
        Decimal("100"),
    )

    assert result == Decimal("0")


def test_analytics_metric():
    metric = AnalyticsMetric(
        name="return",
        value=Decimal("0.1"),
        category="performance",
    )

    assert metric.name == "return"
    assert metric.value == Decimal("0.1")
    assert metric.category == "performance"


def test_portfolio_kpi():
    kpi = PortfolioKPI(
        nav=Decimal("100000"),
        return_rate=Decimal("0.1"),
        risk=Decimal("0.05"),
        sharpe=Decimal("2"),
    )

    assert kpi.nav == Decimal("100000")
    assert kpi.return_rate == Decimal("0.1")
    assert kpi.risk == Decimal("0.05")
    assert kpi.sharpe == Decimal("2")


def test_risk_metric():
    risk = RiskMetric(
        var=Decimal("0.02"),
        volatility=Decimal("0.15"),
        drawdown=Decimal("0.1"),
    )

    assert risk.var == Decimal("0.02")
    assert risk.volatility == Decimal("0.15")
    assert risk.drawdown == Decimal("0.1")


def test_performance_metric():
    performance = PerformanceMetric(
        total_return=Decimal("0.15"),
        win_rate=Decimal("0.6"),
        sharpe_ratio=Decimal("1.8"),
    )

    assert performance.total_return == Decimal("0.15")
    assert performance.win_rate == Decimal("0.6")
    assert performance.sharpe_ratio == Decimal("1.8")


def test_analytics_engine():
    calculator = KPICalculator()
    engine = PortfolioAnalyticsEngine(calculator)

    result = engine.generate([Decimal("100"), Decimal("110")])

    assert "return" in result
    assert "current_nav" in result
    assert result["return"] == Decimal("0.1")


def test_analytics_service():
    calculator = KPICalculator()
    engine = PortfolioAnalyticsEngine(calculator)
    service = PortfolioAnalyticsService(engine)

    result = service.snapshot([Decimal("100"), Decimal("110")])

    assert "return" in result


def test_dashboard_snapshot():
    snapshot = DashboardSnapshot(
        performance={"return": Decimal("0.1")},
        risk={"volatility": Decimal("0.15")},
        strategy={"alpha": Decimal("0.05")},
    )

    assert isinstance(snapshot.performance, dict)
    assert isinstance(snapshot.risk, dict)
    assert isinstance(snapshot.strategy, dict)