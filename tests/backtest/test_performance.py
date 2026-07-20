from services.backtest import (
    BenchmarkComparator,
    TradeStatistics,
    PerformanceMetrics,
    DrawdownAnalyzer,
    PerformanceAnalyzer,
    AnalyticsService,
)


def test_trade_statistics():
    statistics = TradeStatistics()

    result = statistics.summarize([1, 2, 3, 4])

    assert result["trade_count"] == 4


def test_benchmark_compare():
    comparator = BenchmarkComparator()

    alpha = comparator.compare(0.18, 0.12)

    assert alpha == 0.06


def test_performance_metrics():
    metrics = PerformanceMetrics(
        total_return=0.25,
        annual_return=0.12,
        sharpe_ratio=1.5,
    )

    assert metrics.total_return == 0.25
    assert metrics.annual_return == 0.12
    assert metrics.sharpe_ratio == 1.5


def test_drawdown_analyzer():
    analyzer = DrawdownAnalyzer()

    drawdown = analyzer.calculate([100, 95, 90, 95, 100])

    assert drawdown == 0.0


def test_performance_analyzer():
    statistics = TradeStatistics()
    analyzer = PerformanceAnalyzer(statistics)

    result = analyzer.analyze([1, 2, 3])

    assert result["trade_count"] == 3


def test_analytics_service():
    statistics = TradeStatistics()
    analyzer = PerformanceAnalyzer(statistics)
    service = AnalyticsService(analyzer)

    result = service.evaluate([1, 2, 3, 4, 5])

    assert result["trade_count"] == 5