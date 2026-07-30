"""Tests for Portfolio Optimizer."""

import pytest
from services.portfolio_management.optimizer import (
    PortfolioOptimizer, OptimizationConfig, OptimizationMethod,
    OptimizationObjective, OptimalPortfolio,
)


class TestPortfolioOptimizer:
    """Test portfolio optimizer."""

    @pytest.fixture
    def optimizer(self):
        config = OptimizationConfig(
            method=OptimizationMethod.MAX_SHARPE,
            max_weight=0.15,
            min_weight=0.01,
            risk_free_rate=0.03,
        )
        return PortfolioOptimizer(config)

    @pytest.fixture
    def sample_returns(self):
        return {
            "AAPL": 0.20,
            "GOOGL": 0.18,
            "MSFT": 0.15,
            "TSLA": 0.35,
            "AMZN": 0.22,
            "META": 0.25,
            "NVDA": 0.40,
            "JPM": 0.10,
            "V": 0.12,
            "WMT": 0.08,
        }

    def test_max_sharpe_optimization(self, optimizer, sample_returns):
        result = optimizer.optimize(sample_returns)
        assert result.position_count > 0
        assert result.expected_return > 0
        assert result.expected_risk > 0
        assert result.expected_sharpe > 0

        # Weights should sum to ~1.0
        total_weight = sum(result.weights.values())
        assert 0.99 <= total_weight <= 1.01

        # Each weight should respect max constraint (allow small floating point tolerance)
        for weight in result.weights.values():
            assert weight <= 0.155, f"Weight {weight} exceeds max"

    def test_minimum_variance(self, sample_returns):
        config = OptimizationConfig(method=OptimizationMethod.MINIMUM_VARIANCE, max_weight=0.20)
        optimizer = PortfolioOptimizer(config)
        result = optimizer.optimize(sample_returns)

        assert result.method == OptimizationMethod.MINIMUM_VARIANCE
        total_weight = sum(result.weights.values())
        assert 0.99 <= total_weight <= 1.01

    def test_risk_parity(self, sample_returns):
        config = OptimizationConfig(method=OptimizationMethod.RISK_PARITY, max_weight=0.20)
        optimizer = PortfolioOptimizer(config)
        result = optimizer.optimize(sample_returns)

        assert result.method == OptimizationMethod.RISK_PARITY
        total_weight = sum(result.weights.values())
        assert 0.99 <= total_weight <= 1.01

    def test_max_diversification(self, sample_returns):
        config = OptimizationConfig(method=OptimizationMethod.MAX_DIVERSIFICATION, max_weight=0.20)
        optimizer = PortfolioOptimizer(config)
        result = optimizer.optimize(sample_returns)

        assert result.method == OptimizationMethod.MAX_DIVERSIFICATION
        assert result.diversification_ratio > 0

    def test_black_litterman(self, sample_returns):
        config = OptimizationConfig(method=OptimizationMethod.BLACK_LITTERMAN, max_weight=0.20)
        optimizer = PortfolioOptimizer(config)
        views = {"NVDA": 0.10, "TSLA": 0.08}
        result = optimizer.optimize(sample_returns, views=views)

        assert result.method == OptimizationMethod.BLACK_LITTERMAN
        total_weight = sum(result.weights.values())
        assert 0.99 <= total_weight <= 1.01

    def test_position_count(self, optimizer, sample_returns):
        result = optimizer.optimize(sample_returns)
        assert result.position_count <= len(sample_returns)
        assert result.position_count > 0

    def test_concentration_hhi(self, optimizer, sample_returns):
        result = optimizer.optimize(sample_returns)
        hhi = result.concentration_hhi
        # HHI: sum of squared weights, max is 1.0 (single stock)
        assert 0 < hhi < 1.0

    def test_top_positions(self, optimizer, sample_returns):
        result = optimizer.optimize(sample_returns)
        top3 = result.get_top_positions(3)
        assert len(top3) == 3
        # Top should be sorted descending
        assert top3[0][1] >= top3[1][1] >= top3[2][1]

    def test_constraint_violations(self, sample_returns):
        config = OptimizationConfig(
            method=OptimizationMethod.MAX_SHARPE,
            max_weight=0.05,  # very restrictive
            min_weight=0.0,
            min_positions=5,
        )
        optimizer = PortfolioOptimizer(config)
        result = optimizer.optimize(sample_returns)

        # With max_weight=0.05, all weights clamped, should have many positions
        assert result.position_count >= 5

    def test_compare_methods(self, sample_returns):
        config = OptimizationConfig(max_weight=0.20)
        optimizer = PortfolioOptimizer(config)
        results = optimizer.compare_methods(sample_returns)

        assert "max_sharpe" in results
        assert "minimum_variance" in results
        assert "risk_parity" in results
        assert "max_diversification" in results

        for method, result in results.items():
            total = sum(result.weights.values())
            assert 0.99 <= total <= 1.01
