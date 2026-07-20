from services.research import (
    PerformanceMetrics,
    TradeStatistics,
    DrawdownAnalyzer,
    BenchmarkComparator,
    PerformanceSummary,
    MetricsService,
)


def test_win_rate():
    stats = TradeStatistics()

    assert stats.win_rate(8, 10) == 0.8


def test_annual_return():
    metrics = PerformanceMetrics()

    assert metrics.annual_return(0.24, 2) == 0.12


def test_max_drawdown():
    analyzer = DrawdownAnalyzer()

    drawdowns = [-0.05, -0.12, -0.08]
    assert analyzer.max_drawdown(drawdowns) == -0.12


def test_excess_return():
    comparator = BenchmarkComparator()

    assert comparator.excess_return(0.20, 0.10) == 0.10


def test_performance_summary():
    summary = PerformanceSummary()

    metrics = {"annual_return": 0.12, "win_rate": 0.8}
    result = summary.build(metrics)

    assert result["status"] == "COMPLETED"
    assert result["metrics"] == metrics


def test_metrics_service():
    summary = PerformanceSummary()
    service = MetricsService(summary)

    metrics = {"annual_return": 0.12}
    result = service.generate(metrics)

    assert result["status"] == "COMPLETED"