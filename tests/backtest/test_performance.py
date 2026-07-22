from services.backtest import (
    BenchmarkComparator,
    TradeStatistics,
    PerformanceMetrics,
    DrawdownAnalyzer,
    PerformanceAnalyzer,
    AnalyticsService,
    ReturnCalculator,
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
        max_drawdown=0.15,
        sharpe_ratio=1.5,
        sortino_ratio=2.0,
    )

    assert metrics.total_return == 0.25
    assert metrics.annual_return == 0.12
    assert metrics.max_drawdown == 0.15
    assert metrics.sharpe_ratio == 1.5
    assert metrics.sortino_ratio == 2.0


def test_drawdown_analyzer():
    analyzer = DrawdownAnalyzer()

    drawdown = analyzer.calculate([100, 95, 90, 95, 100])

    assert drawdown == 0.1


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


def test_return_calculator():
    result = ReturnCalculator().calculate(
        100000,
        110000,
    )

    assert result == 0.10


def test_drawdown():
    drawdown = DrawdownAnalyzer().calculate(
        [
            100,
            120,
            90,
            130,
        ]
    )

    assert drawdown == 0.25