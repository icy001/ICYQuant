import pytest
from datetime import datetime

from research.analytics.equity import EquityCurve, EquityPoint
from research.analytics.metrics import (
    calculate_total_return,
    calculate_returns,
    calculate_max_drawdown,
    calculate_max_drawdown_from_equities,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
)
from research.analytics.benchmark import Benchmark, BenchmarkResult


class TestEquityCurve:

    def test_equity_curve_initialization(self):
        curve = EquityCurve()
        assert len(curve) == 0

    def test_equity_curve_add(self):
        curve = EquityCurve()
        timestamp = datetime(2026, 1, 1)
        curve.add(timestamp, 100000)
        assert len(curve) == 1
        assert curve[0].timestamp == timestamp
        assert curve[0].equity == 100000

    def test_equity_curve_values(self):
        curve = EquityCurve()
        curve.add(datetime(2026, 1, 1), 100000)
        curve.add(datetime(2026, 1, 2), 101000)
        curve.add(datetime(2026, 1, 3), 102000)
        values = curve.values()
        assert values == [100000, 101000, 102000]

    def test_equity_curve_timestamps(self):
        curve = EquityCurve()
        t1 = datetime(2026, 1, 1)
        t2 = datetime(2026, 1, 2)
        curve.add(t1, 100000)
        curve.add(t2, 101000)
        timestamps = curve.timestamps()
        assert timestamps == [t1, t2]


class TestMetrics:

    def test_calculate_total_return(self):
        assert calculate_total_return(100000, 128430) == pytest.approx(0.2843)
        assert calculate_total_return(100000, 100000) == 0.0
        assert calculate_total_return(100000, 90000) == -0.1

    def test_calculate_returns(self):
        equities = [100, 110, 105, 120]
        returns = calculate_returns(equities)
        assert len(returns) == 3
        assert returns[0] == pytest.approx(0.1)
        assert returns[1] == pytest.approx(-0.04545, abs=0.0001)
        assert returns[2] == pytest.approx(0.14286, abs=0.0001)

    def test_calculate_max_drawdown(self):
        equities = [100, 120, 90, 130]
        dd = calculate_max_drawdown_from_equities(equities)
        assert dd == pytest.approx(0.25)

    def test_calculate_max_drawdown_with_tuple_curve(self):
        equity_curve = [
            (datetime(2026, 1, 1), 100),
            (datetime(2026, 1, 2), 120),
            (datetime(2026, 1, 3), 90),
            (datetime(2026, 1, 4), 130),
        ]
        dd = calculate_max_drawdown(equity_curve)
        assert dd == pytest.approx(0.25)

    def test_calculate_sharpe_ratio(self):
        equity_curve = [
            (datetime(2026, 1, 1), 100000),
            (datetime(2026, 1, 2), 101000),
            (datetime(2026, 1, 3), 102000),
            (datetime(2026, 1, 4), 101500),
            (datetime(2026, 1, 5), 103000),
        ]
        sharpe = calculate_sharpe_ratio(equity_curve)
        assert sharpe > 0

    def test_calculate_sortino_ratio(self):
        equity_curve = [
            (datetime(2026, 1, 1), 100000),
            (datetime(2026, 1, 2), 101000),
            (datetime(2026, 1, 3), 99000),
            (datetime(2026, 1, 4), 102000),
            (datetime(2026, 1, 5), 98000),
            (datetime(2026, 1, 6), 103000),
        ]
        sortino = calculate_sortino_ratio(equity_curve)
        assert sortino > 0

    def test_calculate_returns_empty(self):
        assert calculate_returns([]) == []
        assert calculate_returns([100]) == []

    def test_calculate_max_drawdown_empty(self):
        assert calculate_max_drawdown_from_equities([]) == 0.0
        assert calculate_max_drawdown([]) == 0.0

    def test_sharpe_ratio_single_point(self):
        equity_curve = [(datetime(2026, 1, 1), 100000)]
        assert calculate_sharpe_ratio(equity_curve) == 0.0

    def test_sortino_ratio_no_downside(self):
        equity_curve = [
            (datetime(2026, 1, 1), 100000),
            (datetime(2026, 1, 2), 101000),
            (datetime(2026, 1, 3), 102000),
        ]
        assert calculate_sortino_ratio(equity_curve) == 0.0


class TestBenchmark:

    def test_benchmark_initialization(self):
        equity_curve = [
            (datetime(2026, 1, 1), 100),
            (datetime(2026, 1, 2), 105),
        ]
        benchmark = Benchmark("SPY", equity_curve)
        assert benchmark.name == "SPY"
        assert len(benchmark.equity_curve) == 2

    def test_benchmark_calculate_return(self):
        equity_curve = [
            (datetime(2026, 1, 1), 100),
            (datetime(2026, 1, 2), 110),
            (datetime(2026, 1, 3), 115),
        ]
        benchmark = Benchmark("SPY", equity_curve)
        ret = benchmark.calculate_return()
        assert ret == pytest.approx(0.15)

    def test_benchmark_compare(self):
        strategy_curve = [
            (datetime(2026, 1, 1), 100),
            (datetime(2026, 1, 2), 108),
            (datetime(2026, 1, 3), 112),
        ]
        benchmark_curve = [
            (datetime(2026, 1, 1), 100),
            (datetime(2026, 1, 2), 105),
            (datetime(2026, 1, 3), 108),
        ]
        benchmark = Benchmark("SPY", benchmark_curve)
        result = benchmark.compare(strategy_curve)
        
        assert isinstance(result, BenchmarkResult)
        assert result.strategy_return == pytest.approx(0.12)
        assert result.benchmark_return == pytest.approx(0.08)
        assert result.alpha == pytest.approx(0.04)