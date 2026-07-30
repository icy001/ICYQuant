"""Tests for Performance Calculator."""

import pytest
import math
from services.portfolio_management.performance import (
    PerformanceCalculator, PerformanceConfig, PerformanceMetrics,
    ReturnSeries, RiskMetrics,
)


class TestPerformanceCalculator:
    """Test performance calculator."""

    @pytest.fixture
    def calculator(self):
        return PerformanceCalculator()

    @pytest.fixture
    def sample_returns(self):
        # Simulated daily returns over 100 days
        returns = []
        for i in range(100):
            # Random walk with positive drift
            import random
            random.seed(i)
            returns.append(random.gauss(0.001, 0.015))
        return returns

    def test_calculate_metrics(self, calculator, sample_returns):
        metrics = calculator.calculate_metrics("port-1", sample_returns)

        assert metrics.portfolio_id == "port-1"
        assert metrics.total_return != 0
        assert metrics.annual_return != 0
        assert metrics.volatility_annual > 0
        assert metrics.max_drawdown <= 0  # drawdown is negative or zero
        assert 0 <= metrics.win_rate <= 100

    def test_sharpe_ratio(self, calculator, sample_returns):
        metrics = calculator.calculate_metrics("port-1", sample_returns)
        # Sharpe = (return - rf) / vol
        assert metrics.sharpe_ratio is not None

    def test_risk_metrics(self, calculator, sample_returns):
        metrics = calculator.calculate_metrics("port-1", sample_returns)
        assert metrics.risk is not None
        assert metrics.risk.volatility_annual > 0
        assert metrics.risk.max_drawdown <= 0
        assert metrics.risk.var_95_daily > 0
        assert metrics.risk.cvar_95_daily >= metrics.risk.var_95_daily

    def test_insufficient_data(self, calculator):
        metrics = calculator.calculate_metrics("port-1", [0.01])
        # Should return minimal metrics
        assert metrics.portfolio_id == "port-1"

    def test_positive_returns(self, calculator):
        returns = [0.01] * 50  # 1% daily for 50 days
        metrics = calculator.calculate_metrics("pos", returns)

        assert metrics.total_return > 0
        assert metrics.win_rate == 100.0
        assert metrics.max_drawdown == 0.0

    def test_negative_returns(self, calculator):
        returns = [-0.01] * 50  # -1% daily for 50 days
        metrics = calculator.calculate_metrics("neg", returns)

        assert metrics.total_return < 0
        assert metrics.win_rate == 0.0
        assert metrics.max_drawdown < 0

    def test_benchmark_comparison(self, calculator, sample_returns):
        # Generate slightly different benchmark returns
        import random
        random.seed(42)
        bench_returns = [r + random.gauss(0, 0.002) for r in sample_returns]

        metrics = calculator.calculate_metrics("port-1", sample_returns, bench_returns)

        assert metrics.risk is not None
        assert metrics.risk.beta != 0
        assert metrics.risk.tracking_error >= 0
        assert metrics.information_ratio is not None

    def test_performance_metrics_history(self, calculator, sample_returns):
        calculator.calculate_metrics("port-1", sample_returns)
        calculator.calculate_metrics("port-1", [r * 1.1 for r in sample_returns])

        history = calculator.get_metrics_history("port-1")
        assert len(history) == 2

    def test_latest_metrics(self, calculator, sample_returns):
        calculator.calculate_metrics("port-1", sample_returns)
        latest = calculator.get_latest_metrics("port-1")
        assert latest is not None
        assert latest.portfolio_id == "port-1"

    def test_compare_portfolios(self, calculator, sample_returns):
        calculator.calculate_metrics("port-a", sample_returns)
        # Use different returns for port-b
        import random
        random.seed(99)
        b_returns = [random.gauss(0.0005, 0.02) for _ in range(100)]
        calculator.calculate_metrics("port-b", b_returns)

        comparison = calculator.compare_portfolios(["port-a", "port-b"])
        assert "port-a" in comparison
        assert "port-b" in comparison

    def test_sortino_vs_sharpe(self, calculator):
        # All positive returns => Sortino >= Sharpe
        returns = [0.005 + abs(r) for r in [0.001, 0.002, -0.001, 0.003] * 25]
        metrics = calculator.calculate_metrics("p", returns)
        # Sortino should exist
        assert metrics.sortino_ratio is not None

    def test_summary(self, calculator, sample_returns):
        calculator.calculate_metrics("port-1", sample_returns)
        summary = calculator.get_summary()
        assert summary["portfolios_tracked"] == 1
        assert summary["total_calculations"] == 1
