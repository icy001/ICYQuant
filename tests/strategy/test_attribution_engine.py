"""Tests for Strategy Performance Attribution Engine."""

import os
import sys

# Ensure project root is on the path
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from services.strategy_attribution import *


# ========== Helper Data Factories ==========

def _sample_strategy_data():
    """Create sample strategy performance data."""
    return {
        "strategy_name": "AI Momentum",
        "total_return_bps": 120.0,
        "total_return_pct": 0.012,
        "market_return": 0.05,
        "risk_free_rate": 0.02,
        "beta": 1.1,
        "positions": [
            {"symbol": "NVDA", "weight": 0.08, "return": 0.02, "risk_budget_used": 0.08},
            {"symbol": "AAPL", "weight": 0.06, "return": 0.01, "risk_budget_used": 0.06},
            {"symbol": "MSFT", "weight": 0.05, "return": 0.015, "risk_budget_used": 0.05},
            {"symbol": "AMD", "weight": 0.04, "return": 0.025, "risk_budget_used": 0.04},
            {"symbol": "TSM", "weight": 0.03, "return": 0.018, "risk_budget_used": 0.03},
        ],
        "trades": [
            {
                "trade_id": "t1", "symbol": "NVDA", "side": "BUY", "quantity": 100,
                "arrival_price": 800.0, "execution_price": 800.5,
                "slippage_bps": 6.25, "market_impact_bps": 3.0, "commission_bps": 1.0,
            },
            {
                "trade_id": "t2", "symbol": "AAPL", "side": "BUY", "quantity": 200,
                "arrival_price": 175.0, "execution_price": 175.15,
                "slippage_bps": 2.0, "market_impact_bps": 1.5, "commission_bps": 1.0,
            },
            {
                "trade_id": "t3", "symbol": "MSFT", "side": "SELL", "quantity": 150,
                "arrival_price": 400.0, "execution_price": 399.5,
                "slippage_bps": -5.0, "market_impact_bps": 2.0, "commission_bps": 1.0,
            },
        ],
        "factor_exposures": {
            "momentum": 0.30,
            "growth": 0.50,
            "quality": 0.40,
            "value": -0.10,
            "volatility": 0.20,
        },
        "factor_returns": {
            "momentum": 0.04,
            "growth": 0.06,
            "quality": 0.02,
            "value": -0.01,
            "volatility": -0.005,
        },
        "sector_allocations": [
            {"sector": "Technology", "allocation_weight": 0.45, "benchmark_weight": 0.30, "sector_return": 0.06},
            {"sector": "Financials", "allocation_weight": 0.20, "benchmark_weight": 0.25, "sector_return": 0.03},
            {"sector": "Healthcare", "allocation_weight": 0.15, "benchmark_weight": 0.15, "sector_return": 0.04},
            {"sector": "Energy", "allocation_weight": 0.10, "benchmark_weight": 0.15, "sector_return": -0.02},
            {"sector": "Consumer", "allocation_weight": 0.10, "benchmark_weight": 0.15, "sector_return": 0.01},
        ],
        "risk_data": {
            "stop_loss_cost_bps": 3.0,
            "hedging_cost_bps": 2.0,
            "constraint_penalty_bps": 0.0,
        },
    }


def _sample_strategy_data_2():
    """Create second sample strategy data."""
    return {
        "strategy_name": "Value Rotation",
        "total_return_bps": 80.0,
        "market_return": 0.05,
        "risk_free_rate": 0.02,
        "beta": 0.85,
        "positions": [
            {"symbol": "JPM", "weight": 0.07, "return": 0.012, "risk_budget_used": 0.07},
            {"symbol": "XOM", "weight": 0.06, "return": 0.008, "risk_budget_used": 0.06},
            {"symbol": "BAC", "weight": 0.05, "return": 0.015, "risk_budget_used": 0.05},
        ],
        "trades": [
            {
                "trade_id": "t1", "symbol": "JPM", "side": "BUY", "quantity": 150,
                "arrival_price": 150.0, "execution_price": 150.3,
                "slippage_bps": 8.0, "market_impact_bps": 4.0, "commission_bps": 1.0,
            },
        ],
        "factor_exposures": {
            "value": 0.60,
            "momentum": -0.20,
            "quality": 0.30,
            "size": 0.15,
        },
        "factor_returns": {
            "value": 0.03,
            "momentum": -0.02,
            "quality": 0.01,
            "size": 0.005,
        },
        "sector_allocations": [
            {"sector": "Financials", "allocation_weight": 0.40, "benchmark_weight": 0.25, "sector_return": 0.03},
            {"sector": "Energy", "allocation_weight": 0.30, "benchmark_weight": 0.15, "sector_return": 0.01},
        ],
        "risk_data": {
            "stop_loss_cost_bps": 5.0,
            "hedging_cost_bps": 1.0,
            "constraint_penalty_bps": 0.0,
        },
    }


def _sample_minimal_data():
    """Minimal strategy data for edge case testing."""
    return {
        "strategy_name": "Minimal Strategy",
        "total_return_bps": 50.0,
    }


def _sample_negative_data():
    """Strategy data with negative returns."""
    return {
        "strategy_name": "Negative Strategy",
        "total_return_bps": -80.0,
        "market_return": -0.03,
        "risk_free_rate": 0.02,
        "beta": 1.2,
        "positions": [
            {"symbol": "LOST", "weight": 0.10, "return": -0.05, "risk_budget_used": 0.10},
        ],
        "trades": [
            {
                "trade_id": "t1", "symbol": "LOST", "side": "SELL", "quantity": 100,
                "arrival_price": 100.0, "execution_price": 98.0,
                "slippage_bps": -80.0, "market_impact_bps": 20.0, "commission_bps": 2.0,
            },
        ],
        "factor_exposures": {"momentum": 0.80},
        "factor_returns": {"momentum": -0.08},
    }


# ========== 1. Attribution Models ==========

def test_performance_attribution_creation():
    attr = PerformanceAttribution(
        strategy_id="test_001",
        period="2026-Q3",
        period_type=AttributionPeriod.QUARTERLY,
        total_return_bps=120.0,
        total_return_pct=0.012,
        alpha_return_bps=80.0,
        beta_return_bps=50.0,
        factor_return_bps=40.0,
        sector_return_bps=30.0,
        position_sizing_bps=20.0,
        execution_return_bps=-10.0,
        risk_adjustment_bps=-5.0,
        residual_bps=5.0,
    )
    assert attr.strategy_id == "test_001"
    assert attr.total_return_bps == 120.0
    assert attr.alpha_return_bps == 80.0


def test_performance_attribution_to_dict():
    attr = PerformanceAttribution(
        strategy_id="test_001",
        period="2026-Q3",
        period_type=AttributionPeriod.QUARTERLY,
        total_return_bps=120.0,
        total_return_pct=0.012,
        alpha_return_bps=80.0,
        beta_return_bps=50.0,
        factor_return_bps=40.0,
        sector_return_bps=30.0,
        position_sizing_bps=20.0,
        execution_return_bps=-10.0,
        risk_adjustment_bps=-5.0,
        residual_bps=5.0,
    )
    d = attr.to_dict()
    assert d["strategy_id"] == "test_001"
    assert d["total_return_bps"] == 120.0
    assert d["alpha_return_bps"] == 80.0
    assert "components" in d
    assert "factor_exposures" in d


def test_return_component_creation():
    comp = ReturnComponent(
        source=AttributionSource.ALPHA,
        contribution_bps=80.0,
        weight_pct=66.7,
        return_contribution_pct=66.7,
        explanation="Pure alpha from signal",
        confidence=0.85,
    )
    assert comp.source == AttributionSource.ALPHA
    assert comp.contribution_bps == 80.0
    assert comp.confidence == 0.85


def test_factor_exposure_creation():
    fe = FactorExposure(
        category=FactorCategory.MOMENTUM,
        exposure=0.30,
        return_contribution_bps=12.0,
        factor_return=0.04,
        t_stat=2.5,
        significance="SIGNIFICANT",
    )
    assert fe.category == FactorCategory.MOMENTUM
    assert fe.significance == "SIGNIFICANT"


def test_sector_contribution_creation():
    sc = SectorContribution(
        sector="Technology",
        allocation_weight=0.45,
        benchmark_weight=0.30,
        active_weight=0.15,
        sector_return=0.06,
        contribution_bps=9.0,
    )
    assert sc.active_weight == 0.15
    assert sc.contribution_bps == 9.0


def test_trade_attribution_creation():
    ta = TradeAttribution(
        trade_id="t1",
        symbol="NVDA",
        side="BUY",
        quantity=100,
        arrival_price=800.0,
        execution_price=800.5,
        slippage_bps=6.25,
        market_impact_bps=3.0,
        commission_bps=1.0,
        total_cost_bps=10.25,
        quality=TradeQuality.GOOD,
    )
    assert ta.symbol == "NVDA"
    assert ta.quality == TradeQuality.GOOD


def test_position_contribution_creation():
    pc = PositionContribution(
        symbol="NVDA",
        weight=0.08,
        return_pct=0.02,
        contribution_bps=16.0,
        is_overweight=True,
        risk_budget_used=0.08,
    )
    assert pc.is_overweight is True
    assert pc.contribution_bps == 16.0


def test_multi_strategy_attribution_to_dict():
    attr1 = PerformanceAttribution(
        strategy_id="s1", period="Q3", period_type=AttributionPeriod.QUARTERLY,
        total_return_bps=100.0, total_return_pct=0.01,
        alpha_return_bps=60.0, beta_return_bps=30.0, factor_return_bps=10.0,
        sector_return_bps=0.0, position_sizing_bps=0.0,
        execution_return_bps=0.0, risk_adjustment_bps=0.0, residual_bps=0.0,
    )
    multi = MultiStrategyAttribution(
        portfolio_id="folio_1",
        period="2026-Q3",
        total_return_bps=100.0,
        strategy_attributions=[attr1],
    )
    d = multi.to_dict()
    assert d["portfolio_id"] == "folio_1"
    assert len(d["strategy_attributions"]) == 1


def test_attribution_summary_to_dict():
    summary = AttributionSummary(
        strategy_id="s1",
        period="2026-Q3",
        headline="Strong alpha performance",
        key_drivers=["Alpha: +80bps"],
        key_detractors=["Execution: -10bps"],
        recommendation="Increase allocation",
        alpha_quality="STRONG",
        risk_efficiency="EFFICIENT",
    )
    d = summary.to_dict()
    assert d["alpha_quality"] == "STRONG"
    assert d["risk_efficiency"] == "EFFICIENT"


# ========== 2. Attribution Calculator ==========

def test_calculator_basic():
    calc = AttributionCalculator()
    result = calc.calculate(
        strategy_id="alpha_001",
        period="2026-Q3",
        strategy_data=_sample_strategy_data(),
        period_type=AttributionPeriod.QUARTERLY,
    )
    assert result.strategy_id == "alpha_001"
    assert result.period == "2026-Q3"
    assert result.status == AttributionStatus.COMPLETED
    assert result.total_return_bps == 120.0
    assert len(result.components) >= 7


def test_calculator_alpha_calculation():
    calc = AttributionCalculator()
    result = calc.calculate(
        strategy_id="test",
        period="daily",
        strategy_data=_sample_strategy_data(),
    )
    # Alpha = Total - Beta * (Market - RiskFree)
    # Market = 0.05 * 10000 = 500 bps, RF = 0.02 * 10000 = 200 bps
    # Excess = 300 bps, Beta * Excess = 1.1 * 300 = 330 bps
    # Alpha = 120 - 330 = -210 bps
    expected_alpha = round(120.0 - 1.1 * (0.05 - 0.02) * 10000.0, 2)
    assert result.alpha_return_bps == expected_alpha


def test_calculator_beta_calculation():
    calc = AttributionCalculator()
    result = calc.calculate(
        strategy_id="test",
        period="daily",
        strategy_data=_sample_strategy_data(),
    )
    # Beta contribution = 1.1 * 500 bps = 550 bps
    expected_beta = round(1.1 * 0.05 * 10000.0, 2)
    assert result.beta_return_bps == expected_beta


def test_calculator_factor_attribution():
    calc = AttributionCalculator()
    result = calc.calculate(
        strategy_id="test",
        period="daily",
        strategy_data=_sample_strategy_data(),
    )
    assert len(result.factor_exposures) == 5
    for fe in result.factor_exposures:
        assert fe.category is not None
        assert fe.significance in ("SIGNIFICANT", "MODERATE", "WEAK")


def test_calculator_sector_attribution():
    calc = AttributionCalculator()
    result = calc.calculate(
        strategy_id="test",
        period="daily",
        strategy_data=_sample_strategy_data(),
    )
    assert len(result.sector_contributions) == 5
    tech = next(s for s in result.sector_contributions if s.sector == "Technology")
    assert tech.active_weight == 0.15
    assert tech.contribution_bps == round(0.15 * 0.06 * 10000, 2)


def test_calculator_position_contribution():
    calc = AttributionCalculator()
    result = calc.calculate(
        strategy_id="test",
        period="daily",
        strategy_data=_sample_strategy_data(),
    )
    assert len(result.position_contributions) == 5
    nvda = next(p for p in result.position_contributions if p.symbol == "NVDA")
    # Equal weight = 1/5 = 0.2, NVDA weight = 0.08 < 0.2, so underweight
    assert nvda.weight == 0.08


def test_calculator_execution_contribution():
    calc = AttributionCalculator()
    result = calc.calculate(
        strategy_id="test",
        period="daily",
        strategy_data=_sample_strategy_data(),
    )
    assert len(result.trade_attributions) == 3
    # Execution costs can be negative (good for returns) if we sell at better price
    # Verify trade quality grading exists
    qualities = {t.quality for t in result.trade_attributions}
    assert len(qualities) > 0


def test_calculator_risk_penalty():
    calc = AttributionCalculator()
    result = calc.calculate(
        strategy_id="test",
        period="daily",
        strategy_data=_sample_strategy_data(),
    )
    assert result.risk_adjustment_bps <= 0  # Risk is always a cost
    # stop_loss(3) + hedging(2) + constraint(0) = -5 bps
    assert result.risk_adjustment_bps == -5.0


def test_calculator_residual():
    calc = AttributionCalculator()
    result = calc.calculate(
        strategy_id="test",
        period="daily",
        strategy_data=_sample_strategy_data(),
    )
    sum_components = (
        result.alpha_return_bps + result.beta_return_bps + result.factor_return_bps
        + result.sector_return_bps + result.position_sizing_bps
        + result.execution_return_bps + result.risk_adjustment_bps
    )
    assert round(sum_components + result.residual_bps, 2) == result.total_return_bps


def test_calculator_minimal_data():
    calc = AttributionCalculator()
    result = calc.calculate(
        strategy_id="minimal",
        period="daily",
        strategy_data=_sample_minimal_data(),
    )
    assert result.total_return_bps == 50.0
    assert result.status == AttributionStatus.COMPLETED
    assert len(result.components) > 0


def test_calculator_negative_returns():
    calc = AttributionCalculator()
    result = calc.calculate(
        strategy_id="neg",
        period="daily",
        strategy_data=_sample_negative_data(),
    )
    assert result.total_return_bps == -80.0
    assert result.status == AttributionStatus.COMPLETED
    # Verify attribution works for negative returns too
    assert result.alpha_return_bps is not None
    assert result.beta_return_bps is not None


def test_calculator_get_attribution():
    calc = AttributionCalculator()
    result = calc.calculate(
        strategy_id="test",
        period="daily",
        strategy_data=_sample_strategy_data(),
    )
    found = calc.get_attribution(result.attribution_id)
    assert found is not None
    assert found.strategy_id == "test"


def test_calculator_get_attribution_not_found():
    calc = AttributionCalculator()
    found = calc.get_attribution("nonexistent")
    assert found is None


def test_calculator_get_history():
    calc = AttributionCalculator()
    calc.calculate(strategy_id="s1", period="p1", strategy_data=_sample_strategy_data())
    calc.calculate(strategy_id="s1", period="p2", strategy_data=_sample_strategy_data())
    calc.calculate(strategy_id="s2", period="p1", strategy_data=_sample_strategy_data_2())

    all_history = calc.get_history()
    assert len(all_history) == 3

    s1_history = calc.get_history(strategy_id="s1")
    assert len(s1_history) == 2


def test_calculator_compare_periods():
    calc = AttributionCalculator()
    calc.calculate(strategy_id="s1", period="Q1", strategy_data=_sample_strategy_data())
    calc.calculate(strategy_id="s1", period="Q2", strategy_data=_sample_strategy_data_2())

    comparison = calc.compare_periods("s1", "Q1", "Q2")
    assert "return_change_bps" in comparison
    assert "alpha_change_bps" in comparison
    assert comparison["strategy_id"] == "s1"


def test_calculator_compare_periods_not_found():
    calc = AttributionCalculator()
    comparison = calc.compare_periods("s1", "Q1", "Q2")
    assert "error" in comparison


# ========== 3. Strategy Analyzer ==========

def test_analyzer_analyze():
    calc = AttributionCalculator()
    attr = calc.calculate(
        strategy_id="alpha_001",
        period="2026-Q3",
        strategy_data=_sample_strategy_data(),
    )

    analyzer = StrategyAnalyzer()
    analysis = analyzer.analyze(attr)

    assert "analysis_id" in analysis
    assert "return_analysis" in analysis
    assert "risk_analysis" in analysis
    assert "trade_analysis" in analysis
    assert "key_drivers" in analysis
    assert "key_detractors" in analysis
    assert "alpha_quality" in analysis
    assert "risk_efficiency" in analysis
    assert "recommendation" in analysis


def test_analyzer_return_analysis():
    calc = AttributionCalculator()
    attr = calc.calculate(
        strategy_id="test",
        period="daily",
        strategy_data=_sample_strategy_data(),
    )

    analyzer = StrategyAnalyzer()
    analysis = analyzer.analyze(attr)

    ra = analysis["return_analysis"]
    assert "total_return_bps" in ra
    assert "alpha_ratio" in ra
    assert "beta_ratio" in ra
    assert "factor_ratio" in ra
    assert "is_alpha_driven" in ra
    assert "is_beta_driven" in ra


def test_analyzer_risk_analysis():
    calc = AttributionCalculator()
    attr = calc.calculate(
        strategy_id="test",
        period="daily",
        strategy_data=_sample_strategy_data(),
    )

    analyzer = StrategyAnalyzer()
    analysis = analyzer.analyze(attr)

    ra = analysis["risk_analysis"]
    assert "factor_concentration" in ra
    assert "sector_concentration" in ra
    assert "position_concentration" in ra
    assert "high_concentration_risk" in ra


def test_analyzer_trade_analysis():
    calc = AttributionCalculator()
    attr = calc.calculate(
        strategy_id="test",
        period="daily",
        strategy_data=_sample_strategy_data(),
    )

    analyzer = StrategyAnalyzer()
    analysis = analyzer.analyze(attr)

    ta = analysis["trade_analysis"]
    assert ta["total_trades"] == 3
    assert "avg_cost_bps" in ta
    assert "quality_distribution" in ta
    assert "execution_efficiency" in ta


def test_analyzer_summarize():
    calc = AttributionCalculator()
    attr = calc.calculate(
        strategy_id="alpha_001",
        period="2026-Q3",
        strategy_data=_sample_strategy_data(),
    )

    analyzer = StrategyAnalyzer()
    summary = analyzer.summarize(attr)

    assert isinstance(summary, AttributionSummary)
    assert summary.strategy_id == "alpha_001"
    assert len(summary.headline) > 0
    assert len(summary.recommendation) > 0
    assert summary.alpha_quality in ("STRONG", "MODERATE", "WEAK", "NEGATIVE")
    assert summary.risk_efficiency in ("EFFICIENT", "ADEQUATE", "INEFFICIENT")


def test_analyzer_get_analysis():
    calc = AttributionCalculator()
    attr = calc.calculate(
        strategy_id="test",
        period="daily",
        strategy_data=_sample_strategy_data(),
    )

    analyzer = StrategyAnalyzer()
    analysis = analyzer.analyze(attr)
    found = analyzer.get_analysis(analysis["analysis_id"])
    assert found is not None
    assert found["strategy_id"] == "test"


def test_analyzer_get_analysis_not_found():
    analyzer = StrategyAnalyzer()
    found = analyzer.get_analysis("nonexistent")
    assert found is None


def test_analyzer_driver_identification():
    calc = AttributionCalculator()
    attr = calc.calculate(
        strategy_id="test",
        period="daily",
        strategy_data=_sample_strategy_data(),
    )

    analyzer = StrategyAnalyzer()
    analysis = analyzer.analyze(attr)

    # Should have some drivers or detractors
    assert len(analysis["key_drivers"]) > 0 or len(analysis["key_detractors"]) > 0


def test_analyzer_negative_returns():
    calc = AttributionCalculator()
    attr = calc.calculate(
        strategy_id="neg",
        period="daily",
        strategy_data=_sample_negative_data(),
    )

    analyzer = StrategyAnalyzer()
    analysis = analyzer.analyze(attr)

    # Alpha can be positive even with negative total return
    # (e.g., alpha = total - beta * (market - rf): -80 - 1.2*(-300-200) = 520 > 0)
    assert analysis["alpha_quality"] in ("MODERATE", "NEGATIVE", "WEAK", "STRONG")
    assert len(analysis["key_detractors"]) > 0


def test_analyzer_minimal_data():
    calc = AttributionCalculator()
    attr = calc.calculate(
        strategy_id="minimal",
        period="daily",
        strategy_data=_sample_minimal_data(),
    )

    analyzer = StrategyAnalyzer()
    analysis = analyzer.analyze(attr)

    assert analysis["trade_analysis"]["total_trades"] == 0
    assert "recommendation" in analysis


# ========== 4. StrategyAttributionService ==========

def test_service_attribute():
    service = StrategyAttributionService()
    result = service.attribute(
        strategy_id="alpha_001",
        period="2026-Q3",
        strategy_data=_sample_strategy_data(),
        period_type=AttributionPeriod.QUARTERLY,
    )

    assert "attribution" in result
    assert "analysis" in result
    assert "summary" in result
    assert result["attribution"]["strategy_id"] == "alpha_001"


def test_service_get_attribution():
    service = StrategyAttributionService()
    result = service.attribute(
        strategy_id="test",
        period="daily",
        strategy_data=_sample_strategy_data(),
    )
    attr_id = result["attribution"]["attribution_id"]

    found = service.get_attribution(attr_id)
    assert found is not None
    assert found["strategy_id"] == "test"


def test_service_get_history():
    service = StrategyAttributionService()
    service.attribute(strategy_id="s1", period="p1", strategy_data=_sample_strategy_data())
    service.attribute(strategy_id="s1", period="p2", strategy_data=_sample_strategy_data_2())
    service.attribute(strategy_id="s2", period="p1", strategy_data=_sample_strategy_data())

    all_history = service.get_history()
    assert len(all_history) == 3

    s1_history = service.get_history(strategy_id="s1")
    assert len(s1_history) == 2


def test_service_compare_periods():
    service = StrategyAttributionService()
    service.attribute(strategy_id="s1", period="Q1", strategy_data=_sample_strategy_data())
    service.attribute(strategy_id="s1", period="Q2", strategy_data=_sample_strategy_data_2())

    comparison = service.compare_periods("s1", "Q1", "Q2")
    assert "return_change_bps" in comparison
    assert "alpha_change_bps" in comparison


def test_service_attribute_multi_strategy():
    service = StrategyAttributionService()
    result = service.attribute_multi_strategy(
        portfolio_id="folio_1",
        period="2026-Q3",
        strategies_data=[
            {"strategy_id": "alpha_001", "data": _sample_strategy_data()},
            {"strategy_id": "value_002", "data": _sample_strategy_data_2()},
        ],
    )

    assert "attribution" in result
    assert "analysis" in result
    attr = result["attribution"]
    assert len(attr["strategy_attributions"]) == 2
    assert attr["portfolio_id"] == "folio_1"
    assert "correlation_matrix" in attr
    assert "top_contributors" in attr
    assert "bottom_contributors" in attr


def test_service_multi_strategy_analysis():
    service = StrategyAttributionService()
    result = service.attribute_multi_strategy(
        portfolio_id="folio_1",
        period="2026-Q3",
        strategies_data=[
            {"strategy_id": "alpha_001", "data": _sample_strategy_data()},
            {"strategy_id": "value_002", "data": _sample_strategy_data_2()},
        ],
    )

    analysis = result["analysis"]
    assert "alpha_generating_strategies" in analysis
    assert "beta_exposed_strategies" in analysis
    assert "recommendation" in analysis


def test_service_single_strategy_multi():
    service = StrategyAttributionService()
    result = service.attribute_multi_strategy(
        portfolio_id="solo",
        period="2026-Q3",
        strategies_data=[
            {"strategy_id": "alpha_001", "data": _sample_strategy_data()},
        ],
    )
    assert len(result["attribution"]["strategy_attributions"]) == 1


# ========== 5. Edge Cases and Validation ==========

def test_empty_positions():
    data = _sample_strategy_data()
    data["positions"] = []
    calc = AttributionCalculator()
    result = calc.calculate(strategy_id="test", period="daily", strategy_data=data)
    assert len(result.position_contributions) == 0
    assert result.position_sizing_bps == 0.0


def test_empty_trades():
    data = _sample_strategy_data()
    data["trades"] = []
    calc = AttributionCalculator()
    result = calc.calculate(strategy_id="test", period="daily", strategy_data=data)
    assert len(result.trade_attributions) == 0
    assert result.execution_return_bps == 0.0


def test_empty_factor_exposures():
    data = _sample_strategy_data()
    data["factor_exposures"] = {}
    calc = AttributionCalculator()
    result = calc.calculate(strategy_id="test", period="daily", strategy_data=data)
    assert len(result.factor_exposures) == 0
    assert result.factor_return_bps == 0.0


def test_empty_sector_allocations():
    data = _sample_strategy_data()
    data["sector_allocations"] = []
    calc = AttributionCalculator()
    result = calc.calculate(strategy_id="test", period="daily", strategy_data=data)
    assert len(result.sector_contributions) == 0
    assert result.sector_return_bps == 0.0


def test_zero_total_return():
    data = _sample_strategy_data()
    data["total_return_bps"] = 0.0
    data.pop("total_return_pct", None)  # Remove to avoid fallback
    calc = AttributionCalculator()
    result = calc.calculate(strategy_id="test", period="daily", strategy_data=data)
    assert result.total_return_bps == 0.0


def test_calculator_confidence_scoring():
    calc = AttributionCalculator()
    # Full data -> high confidence
    result_full = calc.calculate(
        strategy_id="test", period="daily", strategy_data=_sample_strategy_data()
    )
    # Minimal data -> lower confidence
    result_min = calc.calculate(
        strategy_id="test", period="daily", strategy_data=_sample_minimal_data()
    )
    assert result_full.confidence_score > result_min.confidence_score


def test_factor_custom_category():
    data = _sample_strategy_data()
    data["factor_exposures"] = {"custom_factor_xyz": 0.45}
    data["factor_returns"] = {"custom_factor_xyz": 0.03}
    calc = AttributionCalculator()
    result = calc.calculate(strategy_id="test", period="daily", strategy_data=data)
    assert len(result.factor_exposures) == 1
    assert result.factor_exposures[0].category == FactorCategory.CUSTOM


def test_service_history_empty():
    service = StrategyAttributionService()
    history = service.get_history()
    assert history == []


def test_trade_quality_grading():
    calc = AttributionCalculator()
    data = {
        "total_return_bps": 100.0,
        "trades": [
            {"trade_id": "t_excellent", "symbol": "A", "side": "BUY", "quantity": 100,
             "arrival_price": 100.0, "execution_price": 100.0,
             "slippage_bps": 1.0, "market_impact_bps": 1.0, "commission_bps": 1.0},
            {"trade_id": "t_poor", "symbol": "B", "side": "SELL", "quantity": 100,
             "arrival_price": 100.0, "execution_price": 98.0,
             "slippage_bps": 20.0, "market_impact_bps": 15.0, "commission_bps": 2.0},
        ],
    }
    result = calc.calculate(strategy_id="test", period="daily", strategy_data=data)
    qualities = {t.trade_id: t.quality for t in result.trade_attributions}
    assert qualities["t_excellent"] == TradeQuality.EXCELLENT
    assert qualities["t_poor"] in (TradeQuality.POOR, TradeQuality.AVERAGE)


def test_enum_values():
    assert AttributionSource.ALPHA.value == "ALPHA"
    assert AttributionSource.MARKET_BETA.value == "MARKET_BETA"
    assert AttributionPeriod.DAILY.value == "DAILY"
    assert FactorCategory.MOMENTUM.value == "MOMENTUM"
    assert TradeQuality.EXCELLENT.value == "EXCELLENT"
    assert AttributionStatus.COMPLETED.value == "COMPLETED"


if __name__ == "__main__":
    import sys

    passed = 0
    failed = 0
    tests = [
        # Models
        test_performance_attribution_creation,
        test_performance_attribution_to_dict,
        test_return_component_creation,
        test_factor_exposure_creation,
        test_sector_contribution_creation,
        test_trade_attribution_creation,
        test_position_contribution_creation,
        test_multi_strategy_attribution_to_dict,
        test_attribution_summary_to_dict,
        # Calculator
        test_calculator_basic,
        test_calculator_alpha_calculation,
        test_calculator_beta_calculation,
        test_calculator_factor_attribution,
        test_calculator_sector_attribution,
        test_calculator_position_contribution,
        test_calculator_execution_contribution,
        test_calculator_risk_penalty,
        test_calculator_residual,
        test_calculator_minimal_data,
        test_calculator_negative_returns,
        test_calculator_get_attribution,
        test_calculator_get_attribution_not_found,
        test_calculator_get_history,
        test_calculator_compare_periods,
        test_calculator_compare_periods_not_found,
        # Analyzer
        test_analyzer_analyze,
        test_analyzer_return_analysis,
        test_analyzer_risk_analysis,
        test_analyzer_trade_analysis,
        test_analyzer_summarize,
        test_analyzer_get_analysis,
        test_analyzer_get_analysis_not_found,
        test_analyzer_driver_identification,
        test_analyzer_negative_returns,
        test_analyzer_minimal_data,
        # Service
        test_service_attribute,
        test_service_get_attribution,
        test_service_get_history,
        test_service_compare_periods,
        test_service_attribute_multi_strategy,
        test_service_multi_strategy_analysis,
        test_service_single_strategy_multi,
        # Edge cases
        test_empty_positions,
        test_empty_trades,
        test_empty_factor_exposures,
        test_empty_sector_allocations,
        test_zero_total_return,
        test_calculator_confidence_scoring,
        test_factor_custom_category,
        test_service_history_empty,
        test_trade_quality_grading,
        test_enum_values,
    ]

    for test in tests:
        try:
            test()
            passed += 1
            print(f"  PASS {test.__name__}")
        except Exception as e:
            failed += 1
            print(f"  FAIL {test.__name__}: {e}")

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    sys.exit(0 if failed == 0 else 1)
