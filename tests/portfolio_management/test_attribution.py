"""Tests for Attribution Engine."""

import pytest
from services.portfolio_management.attribution import (
    AttributionEngine, AttributionConfig, AttributionMethod,
    AttributionResult, BrinsonAttribution, SectorAttribution, FactorAttribution,
)


class TestAttributionEngine:
    """Test performance attribution."""

    @pytest.fixture
    def engine(self):
        config = AttributionConfig(method=AttributionMethod.BRINSON)
        return AttributionEngine(config)

    @pytest.fixture
    def sample_data(self):
        portfolio_weights = {"Financials": 0.25, "Tech": 0.35, "Consumer": 0.15, "Energy": 0.10, "Healthcare": 0.15}
        benchmark_weights = {"Financials": 0.20, "Tech": 0.30, "Consumer": 0.20, "Energy": 0.15, "Healthcare": 0.15}
        portfolio_returns = {"Financials": 0.08, "Tech": 0.25, "Consumer": 0.05, "Energy": 0.12, "Healthcare": 0.10}
        benchmark_returns = {"Financials": 0.10, "Tech": 0.20, "Consumer": 0.08, "Energy": 0.15, "Healthcare": 0.09}
        return portfolio_weights, benchmark_weights, portfolio_returns, benchmark_returns

    def test_brinson_attribution(self, engine, sample_data):
        pw, bw, pr, br = sample_data
        result = engine.attribute_brinson("port-1", pw, bw, pr, br, period="Q1")

        assert result.method == AttributionMethod.BRINSON
        assert result.brinson is not None
        assert isinstance(result.brinson.allocation_effect, float)
        assert isinstance(result.brinson.selection_effect, float)
        assert isinstance(result.brinson.interaction_effect, float)

        # Total should approximate active return
        total = result.brinson.allocation_effect + result.brinson.selection_effect + result.brinson.interaction_effect
        assert abs(total - result.active_return) < 0.01  # close to active return

    def test_sector_details(self, engine, sample_data):
        pw, bw, pr, br = sample_data
        result = engine.attribute_brinson("port-1", pw, bw, pr, br)

        assert len(result.sector_attribution) >= 5

        for sector_attr in result.sector_attribution:
            assert sector_attr.sector_name in pw
            assert sector_attr.portfolio_weight >= 0
            assert sector_attr.benchmark_weight >= 0
            assert sector_attr.total_effect is not None

    def test_top_contributors(self, engine, sample_data):
        pw, bw, pr, br = sample_data
        result = engine.attribute_brinson("port-1", pw, bw, pr, br)

        top3 = result.top_contributors(3, by="total")
        assert len(top3) == 3
        # Should be sorted by absolute effect
        assert abs(top3[0].total_effect) >= abs(top3[-1].total_effect)

    def test_factor_attribution(self, engine):
        factor_exposures = {
            "value": 0.3,
            "momentum": 0.5,
            "size": -0.2,
            "quality": 0.4,
            "volatility": -0.1,
        }
        factor_returns = {
            "value": 0.05,
            "momentum": 0.12,
            "size": -0.03,
            "quality": 0.08,
            "volatility": 0.02,
        }
        engine.config.factors = list(factor_exposures.keys())

        result = engine.attribute_factors("port-1", factor_exposures, factor_returns)
        assert result.method == AttributionMethod.FACTOR_BASED
        assert len(result.factor_attribution) == 5

        # Check contributions
        for fa in result.factor_attribution:
            assert fa.contribution == fa.factor_exposure * fa.factor_return
            assert fa.contribution_pct is not None

    def test_get_results(self, engine, sample_data):
        pw, bw, pr, br = sample_data
        engine.attribute_brinson("port-1", pw, bw, pr, br)
        engine.attribute_brinson("port-2", pw, bw, pr, br)

        results = engine.get_results()
        assert len(results) == 2

        port1_results = engine.get_results(portfolio_id="port-1")
        assert len(port1_results) == 1

    def test_explained_pct(self, engine, sample_data):
        pw, bw, pr, br = sample_data
        result = engine.attribute_brinson("port-1", pw, bw, pr, br)

        # Most of the return should be explained
        assert result.explained_pct > 90 or abs(result.unexplained_return) < 0.01

    def test_summary(self, engine, sample_data):
        pw, bw, pr, br = sample_data
        engine.attribute_brinson("port-1", pw, bw, pr, br)

        summary = engine.get_summary()
        assert summary["total_analyses"] == 1
        assert "brinson" in summary["methods_used"]
