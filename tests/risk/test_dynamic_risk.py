"""Tests for Dynamic Risk Management Engine."""

import math
import random

from services.risk.dynamic import (
    RiskSnapshot, PositionRisk, RiskDecision,
    RiskLevel, RiskAction, MarketRegime,
    RiskThresholds, MarketRegimeSnapshot,
    RiskCalculator, VolatilityTargeter, RiskMonitor, DynamicRiskService,
)
from services.risk.stress import ScenarioEngine, StressSimulator, StressSimulationResult
from services.risk.api import get_risk_snapshot, run_stress_test, get_risk_report_api


# ========== Helper Functions ==========

def _generate_returns(n: int = 252, mean: float = 0.0005, std: float = 0.015) -> list:
    """Generate synthetic return series."""
    random.seed(42)
    return [random.gauss(mean, std) for _ in range(n)]


def _sample_positions() -> dict:
    return {
        "NVDA": 80000.0,
        "AAPL": 60000.0,
        "MSFT": 50000.0,
        "GOOGL": 40000.0,
        "AMZN": 30000.0,
    }


# ========== 1. Risk Models ==========

def test_risk_snapshot_creation():
    snapshot = RiskSnapshot(
        portfolio_id="TEST_FUND",
        timestamp=None,  # will be set in collector
        volatility=0.15,
        var_95=-0.025,
        var_99=-0.042,
        cvar_95=-0.035,
        cvar_99=-0.058,
        drawdown=0.05,
        max_drawdown=0.12,
        exposure={"equity": 0.60, "bonds": 0.15, "cash": 0.25},
        concentration_ratio=0.35,
        sharpe_ratio=1.2,
        risk_level=RiskLevel.NORMAL,
        market_regime=MarketRegime.NORMAL,
    )
    d = snapshot.to_dict()
    assert d["portfolio"] == "TEST_FUND"
    assert d["risk"]["volatility"] == 0.15
    assert d["risk_level"] == "NORMAL"


def test_risk_levels():
    assert RiskLevel.LOW.value == "LOW"
    assert RiskLevel.NORMAL.value == "NORMAL"
    assert RiskLevel.ELEVATED.value == "ELEVATED"
    assert RiskLevel.HIGH.value == "HIGH"
    assert RiskLevel.CRITICAL.value == "CRITICAL"


def test_risk_action():
    assert RiskAction.NONE.value == "NONE"
    assert RiskAction.REDUCE_POSITION.value == "REDUCE_POSITION"
    assert RiskAction.STOP_TRADING.value == "STOP_TRADING"


def test_market_regime():
    assert MarketRegime.NORMAL.value == "NORMAL"
    assert MarketRegime.CRISIS.value == "CRISIS"


def test_position_risk_score():
    risk = PositionRisk(
        symbol="NVDA", weight=0.08, notional=80000.0,
        volatility=0.30, var_95=2400.0, cvar_95=3500.0,
        marginal_risk=0.02, risk_contribution_pct=25.0, beta=1.5,
    )
    score = risk.risk_score()
    assert score > 0
    assert score == 25.0 * 0.30 * (1.5 + 0.5)


def test_risk_decision_to_dict():
    snapshot = RiskSnapshot(
        portfolio_id="FUND1", timestamp=None,
        volatility=0.20, var_95=-0.03, var_99=-0.05,
        cvar_95=-0.04, cvar_99=-0.07, drawdown=0.10,
        max_drawdown=0.15, exposure={}, concentration_ratio=0.30,
        sharpe_ratio=0.8, risk_level=RiskLevel.ELEVATED,
        market_regime=MarketRegime.HIGH_VOL,
    )
    decision = RiskDecision(
        decision_id="DEC_001", portfolio_id="FUND1", timestamp=None,
        risk_snapshot=snapshot, action=RiskAction.REDUCE_POSITION,
        target_exposure={"equity": 0.50}, position_adjustments=[],
        reason="Volatility high", urgency=6, reduction_pct=0.25,
    )
    d = decision.to_dict()
    assert d["action"] == "REDUCE_POSITION"
    assert d["reduction_pct"] == 0.25


def test_risk_thresholds_default():
    t = RiskThresholds()
    assert t.target_volatility == 0.15
    assert t.max_volatility == 0.30
    assert t.max_drawdown == 0.20


def test_risk_thresholds_custom():
    t = RiskThresholds(
        target_volatility=0.12,
        max_volatility=0.25,
        max_drawdown=0.15,
    )
    assert t.target_volatility == 0.12
    assert t.max_volatility == 0.25


def test_market_regime_snapshot():
    snap = MarketRegimeSnapshot(
        regime=MarketRegime.HIGH_VOL,
        confidence=0.85,
        indicators={"vix": 28.0, "spx_drawdown": 0.08},
        transition_probability={"to_normal": 0.3, "to_crisis": 0.2},
    )
    d = snap.to_dict()
    assert d["regime"] == "HIGH_VOL"
    assert d["confidence"] == 0.85


# ========== 2. Risk Calculator (VaR / CVaR) ==========

def test_risk_calculator_basic():
    calc = RiskCalculator()
    returns = _generate_returns(100)
    result = calc.compute_var(returns)
    assert "var_pct" in result
    assert "var_amount" in result
    assert result["method"] == "parametric"
    assert result["confidence"] == 0.95


def test_risk_calculator_var_parametric():
    calc = RiskCalculator()
    returns = [0.001, 0.002, -0.003, 0.001, -0.002, 0.003, -0.001, 0.000, -0.004, 0.002]
    result = calc.compute_var(returns, confidence=0.95, method="parametric")
    assert result["confidence"] == 0.95
    assert result["var_pct"] < 0  # VaR should be negative (loss)


def test_risk_calculator_var_historical():
    calc = RiskCalculator()
    returns = [0.001, 0.002, -0.003, 0.001, -0.002, 0.003, -0.001, 0.000, -0.004, 0.002]
    result = calc.compute_var(returns, confidence=0.95, method="historical")
    assert result["method"] == "historical"


def test_risk_calculator_var_with_position():
    calc = RiskCalculator()
    returns = _generate_returns(100)
    result = calc.compute_var(returns, position_value=1000000.0)
    assert result["var_amount"] > 0


def test_risk_calculator_multi_horizon():
    calc = RiskCalculator()
    returns = _generate_returns(50)
    result = calc.compute_var_multi_horizon(returns, horizons=[1, 5, 10])
    assert "var_1d" in result
    assert "var_5d" in result
    assert "vol_10d" in result
    # Longer horizon should have higher VaR (in absolute value)
    assert abs(result["var_5d"]) >= abs(result["var_1d"])


def test_risk_calculator_cvar():
    calc = RiskCalculator()
    returns = _generate_returns(200)
    result = calc.compute_cvar(returns, confidence=0.95)
    assert "cvar_pct" in result
    assert "cvar_amount" in result
    assert "tail_observations" in result


def test_risk_calculator_cvar_worse_than_var():
    calc = RiskCalculator()
    # Create returns with some large negative values
    returns = [0.001, 0.002, -0.05, 0.001, -0.03, 0.002, -0.04, 0.001, -0.06, 0.001]
    var_result = calc.compute_var(returns, confidence=0.95)
    cvar_result = calc.compute_cvar(returns, confidence=0.95)
    # CVaR should be more negative than VaR with fat tails
    assert cvar_result["cvar_pct"] <= var_result["var_pct"]


def test_risk_calculator_component_var():
    calc = RiskCalculator()
    weights = [0.4, 0.3, 0.3]
    volatilities = [0.25, 0.18, 0.20]
    correlation = [
        [1.0, 0.5, 0.3],
        [0.5, 1.0, 0.4],
        [0.3, 0.4, 1.0],
    ]
    result = calc.compute_component_var(
        weights, volatilities, correlation,
        portfolio_value=1000000.0,
    )
    assert "portfolio_var" in result
    assert "components" in result
    assert len(result["components"]) == 3
    # Sum of risk contributions should approximate 100%
    total_contrib = sum(c["risk_contribution_pct"] for c in result["components"])
    assert 95 <= total_contrib <= 105


def test_risk_calculator_risk_metrics():
    calc = RiskCalculator()
    returns = _generate_returns(252)
    weights = [0.5, 0.3, 0.2]
    volatilities = [0.22, 0.16, 0.20]
    correlation = [
        [1.0, 0.6, 0.4],
        [0.6, 1.0, 0.3],
        [0.4, 0.3, 1.0],
    ]
    result = calc.compute_risk_metrics(
        returns, weights=weights, volatilities=volatilities,
        correlation_matrix=correlation, total_value=1000000.0,
    )
    assert "volatility" in result
    assert "var_95" in result
    assert "var_99" in result
    assert "cvar_95" in result
    assert "annualized_volatility" in result
    assert "var_95_amount" in result


# ========== 3. Volatility Targeting ==========

def test_vol_targeter_basic():
    vt = VolatilityTargeter(target_volatility=0.15)
    result = vt.compute_adjustment(0.25, 1000000.0)
    assert "scale_factor" in result
    assert result["scale_factor"] < 1.0  # High vol → reduce
    assert result["target_position"] < 1000000.0


def test_vol_targeter_low_volatility():
    vt = VolatilityTargeter(target_volatility=0.15)
    result = vt.compute_adjustment(0.08, 1000000.0)
    assert result["scale_factor"] > 1.0  # Low vol → increase
    assert result["target_position"] > 1000000.0


def test_vol_targeter_at_target():
    vt = VolatilityTargeter(target_volatility=0.15)
    result = vt.compute_adjustment(0.15, 1000000.0)
    assert abs(result["scale_factor"] - 1.0) < 0.1


def test_vol_targeter_clamp_to_max():
    vt = VolatilityTargeter(target_volatility=0.15, max_leverage=1.5)
    result = vt.compute_adjustment(0.05, 1000000.0)
    assert result["scale_factor"] <= 1.5


def test_vol_targeter_clamp_to_min():
    vt = VolatilityTargeter(target_volatility=0.15, min_leverage=0.2)
    result = vt.compute_adjustment(1.0, 1000000.0)
    assert result["scale_factor"] >= 0.2


def test_vol_targeter_regime():
    vt = VolatilityTargeter(target_volatility=0.15)
    regime = vt.get_volatility_regime(0.08)
    assert regime["regime"] == "LOW_VOL"

    regime = vt.get_volatility_regime(0.15)
    assert regime["regime"] == "TARGET"

    regime = vt.get_volatility_regime(0.35)
    assert regime["regime"] == "HIGH_VOL"

    regime = vt.get_volatility_regime(0.50)
    assert regime["regime"] == "EXTREME_VOL"


def test_vol_targeter_multi_asset():
    vt = VolatilityTargeter(target_volatility=0.15)
    positions = {"NVDA": 80000.0, "AAPL": 60000.0, "MSFT": 50000.0}
    volatilities = {"NVDA": 0.30, "AAPL": 0.18, "MSFT": 0.20}
    result = vt.compute_multi_asset_adjustment(positions, volatilities)
    assert "portfolio_volatility" in result
    assert "adjustments" in result
    assert len(result["adjustments"]) == 3


def test_vol_targeter_forecast():
    vt = VolatilityTargeter()
    returns = _generate_returns(100)
    forecast = vt.forecast_volatility(returns, method="ewma")
    assert forecast > 0
    forecast_simple = vt.forecast_volatility(returns, method="simple")
    assert forecast_simple > 0


# ========== 4. Risk Monitor ==========

def test_risk_monitor_collect_snapshot():
    monitor = RiskMonitor()
    snapshot = monitor.collect_snapshot(
        portfolio_id="FUND1",
        volatility=0.15, var_95=-0.025, var_99=-0.042,
        cvar_95=-0.035, cvar_99=-0.058,
        drawdown=0.05, max_drawdown=0.12,
        exposure={"equity": 0.60, "cash": 0.40},
        concentration_ratio=0.30, sharpe_ratio=1.2,
    )
    assert snapshot.portfolio_id == "FUND1"
    assert snapshot.risk_level == RiskLevel.NORMAL
    assert monitor.get_latest_snapshot() is not None


def test_risk_monitor_high_risk():
    monitor = RiskMonitor()
    snapshot = monitor.collect_snapshot(
        portfolio_id="FUND2",
        volatility=0.35, var_95=-0.06, var_99=-0.10,
        cvar_95=-0.08, cvar_99=-0.12,
        drawdown=0.20, max_drawdown=0.30,
        exposure={"equity": 0.80},
        concentration_ratio=0.60, sharpe_ratio=-0.5,
    )
    assert snapshot.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)


def test_risk_monitor_critical_risk():
    monitor = RiskMonitor()
    snapshot = monitor.collect_snapshot(
        portfolio_id="FUND3",
        volatility=0.50, var_95=-0.10, var_99=-0.15,
        cvar_95=-0.12, cvar_99=-0.20,
        drawdown=0.30, max_drawdown=0.40,
        exposure={"equity": 0.90},
        concentration_ratio=0.70, sharpe_ratio=-2.0,
    )
    assert snapshot.risk_level == RiskLevel.CRITICAL
    assert snapshot.market_regime == MarketRegime.CRISIS


def test_risk_monitor_position_risk():
    monitor = RiskMonitor()
    monitor.update_position_risk(
        symbol="NVDA", weight=0.08, notional=80000.0,
        volatility=0.30, var_95=2400.0, cvar_95=3500.0,
        marginal_risk=0.02, risk_contribution_pct=25.0, beta=1.5,
    )
    monitor.update_position_risk(
        symbol="AAPL", weight=0.06, notional=60000.0,
        volatility=0.18, var_95=1080.0, cvar_95=1500.0,
        marginal_risk=0.01, risk_contribution_pct=15.0, beta=1.1,
    )
    top = monitor._get_top_contributors(2)
    assert len(top) == 2
    assert top[0]["symbol"] == "NVDA"  # Higher risk contribution


def test_risk_monitor_decision():
    monitor = RiskMonitor()
    monitor.collect_snapshot(
        portfolio_id="FUND1", volatility=0.15, var_95=-0.025, var_99=-0.042,
        cvar_95=-0.035, cvar_99=-0.058,
        drawdown=0.05, max_drawdown=0.12,
        exposure={"equity": 0.60}, concentration_ratio=0.30, sharpe_ratio=1.2,
    )
    decision = monitor.get_risk_decision()
    assert "action" in decision
    assert "risk_level" in decision


def test_risk_monitor_elevated_decision():
    monitor = RiskMonitor()
    monitor.collect_snapshot(
        portfolio_id="FUND2", volatility=0.32, var_95=-0.06, var_99=-0.09,
        cvar_95=-0.08, cvar_99=-0.11,
        drawdown=0.05, max_drawdown=0.10,
        exposure={"equity": 0.70}, concentration_ratio=0.35, sharpe_ratio=0.5,
    )
    decision = monitor.get_risk_decision()
    assert decision["action"] == RiskAction.REDUCE_POSITION.value
    assert decision["reduction_pct"] > 0


def test_risk_monitor_regime_check():
    monitor = RiskMonitor()
    monitor.collect_snapshot(
        portfolio_id="FUND1", volatility=0.15, var_95=-0.02, var_99=-0.04,
        cvar_95=-0.03, cvar_99=-0.05,
        drawdown=0.03, max_drawdown=0.08,
        exposure={"equity": 0.50}, concentration_ratio=0.25, sharpe_ratio=2.0,
    )
    regime = monitor.get_regime()
    assert regime == MarketRegime.NORMAL


def test_risk_monitor_trend():
    monitor = RiskMonitor()
    vols = [0.15, 0.18, 0.22, 0.25, 0.30]
    for i, v in enumerate(vols):
        monitor.collect_snapshot(
            portfolio_id=f"FUND{i}", volatility=v, var_95=-v * 0.15,
            var_99=-v * 0.25, cvar_95=-v * 0.2, cvar_99=-v * 0.3,
            drawdown=i * 0.03, max_drawdown=0.15,
            exposure={"equity": 0.6 + i * 0.05},
            concentration_ratio=0.3 + i * 0.05, sharpe_ratio=1.0 - i * 0.2,
        )
    trend = monitor.get_risk_trend("volatility")
    assert len(trend) == 5
    assert trend[-1] > trend[0]  # Volatility trend increasing


def test_risk_monitor_alerts():
    monitor = RiskMonitor()
    monitor.collect_snapshot(
        portfolio_id="FUND1", volatility=0.35, var_95=-0.06, var_99=-0.10,
        cvar_95=-0.08, cvar_99=-0.12,
        drawdown=0.18, max_drawdown=0.25,
        exposure={"equity": 0.80}, concentration_ratio=0.45, sharpe_ratio=-0.5,
    )
    alerts = monitor.get_alerts()
    assert len(alerts) > 0


def test_risk_monitor_regime_snapshot():
    monitor = RiskMonitor()
    monitor.collect_snapshot(
        portfolio_id="FUND1", volatility=0.18, var_95=-0.03, var_99=-0.05,
        cvar_95=-0.04, cvar_99=-0.06,
        drawdown=0.06, max_drawdown=0.10,
        exposure={"equity": 0.60}, concentration_ratio=0.30, sharpe_ratio=1.0,
    )
    assessment = monitor.get_regime_assessment()
    assert assessment.regime.value in ("NORMAL", "HIGH_VOL")
    assert "volatility" in assessment.indicators


# ========== 5. Stress Testing ==========

def test_stress_scenarios_list():
    engine = ScenarioEngine()
    scenarios = engine.list_scenarios()
    assert len(scenarios) >= 5
    assert "market_crash" in scenarios
    assert "liquidity_crisis" in scenarios


def test_stress_get_scenario():
    engine = ScenarioEngine()
    scenario = engine.get_scenario("market_crash")
    assert scenario is not None
    assert scenario["severity"] == "SEVERE"
    assert "equity" in scenario["market_shock"]


def test_stress_get_nonexistent_scenario():
    engine = ScenarioEngine()
    scenario = engine.get_scenario("nonexistent")
    assert scenario is None


def test_stress_custom_scenario():
    engine = ScenarioEngine()
    custom = engine.define_custom_scenario(
        name="AI Crash",
        description="AI sector crash 25%",
        severity="EXTREME",
        market_shock={"ai_stocks": -0.25, "semiconductor": -0.20},
        volatility_multiplier=4.0,
        duration_days=10,
    )
    assert custom["severity"] == "EXTREME"
    retrieved = engine.get_scenario("ai_crash")
    assert retrieved is not None


def test_stress_by_severity():
    engine = ScenarioEngine()
    severe = engine.get_scenarios_by_severity("SEVERE")
    assert len(severe) >= 1
    for s in severe:
        assert s["severity"] == "SEVERE"


def test_stress_merge_scenarios():
    engine = ScenarioEngine()
    merged = engine.merge_scenarios(
        ["market_crash", "liquidity_crisis"],
        merge_name="Double Crisis",
    )
    assert merged is not None
    assert "equity" in merged["market_shock"]


def test_stress_simulate_single():
    engine = ScenarioEngine()
    simulator = StressSimulator()
    scenario = engine.get_scenario("market_crash")
    positions = _sample_positions()
    result = simulator.simulate(scenario, positions, portfolio_id="FUND1")
    assert result.loss_pct < 0  # Should lose money
    assert result.worst_asset != ""
    assert result.action_required != ""


def test_stress_simulate_sector_shock():
    engine = ScenarioEngine()
    simulator = StressSimulator()
    scenario = engine.get_scenario("sector_shock")
    positions = {"NVDA": 100000.0, "AMD": 50000.0, "AAPL": 30000.0}
    result = simulator.simulate(scenario, positions)
    # NVDA should be hit harder due to semiconductor sector shock
    result_dict = result.to_dict()
    assert "portfolio_impact" in result_dict
    assert result_dict["portfolio_impact"]["loss_pct"] < 0


def test_stress_simulate_all():
    engine = ScenarioEngine()
    simulator = StressSimulator()
    scenarios = [
        engine.get_scenario("market_crash"),
        engine.get_scenario("liquidity_crisis"),
        engine.get_scenario("sector_shock"),
    ]
    scenarios = [s for s in scenarios if s is not None]
    result = simulator.simulate_all(scenarios, _sample_positions())
    assert result["scenarios_run"] > 0
    assert "worst_case_loss" in result


def test_stress_recovery_estimate():
    simulator = StressSimulator()
    # Small loss
    assert simulator._estimate_recovery(0.03) == 5
    # Medium loss
    assert simulator._estimate_recovery(0.12) == 45
    # Large loss
    assert simulator._estimate_recovery(0.25) == 90


def test_stress_determine_action():
    simulator = StressSimulator()
    assert "MONITOR" in simulator._determine_action(0.03)
    assert "REDUCE" in simulator._determine_action(0.12)
    assert "SIGNIFICANTLY" in simulator._determine_action(0.25)


# ========== 6. Dynamic Risk Service ==========

def test_risk_service_initialization():
    service = DynamicRiskService(target_volatility=0.15)
    assert service.calculator is not None
    assert service.vol_targeter is not None
    assert service.monitor is not None


def test_risk_service_assess_risk():
    service = DynamicRiskService()
    returns = _generate_returns(200)
    weights = [0.4, 0.3, 0.2]
    volatilities = [0.25, 0.18, 0.20]
    correlation = [[1.0, 0.5, 0.3], [0.5, 1.0, 0.4], [0.3, 0.4, 1.0]]
    positions = {"A": 400000.0, "B": 300000.0, "C": 200000.0}

    result = service.assess_risk(
        portfolio_id="FUND1",
        returns=returns,
        weights=weights,
        volatilities=volatilities,
        correlation_matrix=correlation,
        positions=positions,
        drawdown=0.05,
        max_drawdown=0.10,
        exposure={"equity": 0.80, "cash": 0.20},
        total_value=900000.0,
    )
    assert "snapshot" in result
    assert "risk_metrics" in result
    assert "volatility_adjustment" in result
    assert "decision" in result
    assert "regime" in result


def test_risk_service_decide_adjustment():
    service = DynamicRiskService()
    returns = _generate_returns(100, std=0.03)  # Higher vol
    positions = _sample_positions()
    result = service.decide_position_adjustment(
        portfolio_id="FUND1",
        current_positions=positions,
        returns=returns,
    )
    assert "action" in result
    assert "position_adjustments" in result


def test_risk_service_stress_test():
    service = DynamicRiskService()
    positions = _sample_positions()
    result = service.run_stress_test(
        portfolio_id="FUND1",
        positions=positions,
        scenarios=["market_crash", "sector_shock"],
    )
    assert "scenarios_run" in result
    assert "results" in result


def test_risk_service_vol_target_apply():
    service = DynamicRiskService()
    positions = _sample_positions()
    volatilities = {"NVDA": 0.30, "AAPL": 0.18, "MSFT": 0.20, "GOOGL": 0.22, "AMZN": 0.25}
    result = service.apply_vol_target(positions, volatilities)
    assert "portfolio_volatility" in result
    assert "adjustments" in result


def test_risk_service_report():
    service = DynamicRiskService()
    service.assess_risk(
        portfolio_id="FUND1",
        returns=_generate_returns(100),
        drawdown=0.03,
        max_drawdown=0.08,
        exposure={"equity": 0.60},
        total_value=500000.0,
    )
    report = service.get_risk_report("FUND1")
    assert "portfolio" in report
    assert "metrics" in report


# ========== 7. API Endpoints ==========

def test_api_risk_snapshot():
    result = get_risk_snapshot("TEST_FUND")
    assert result["portfolio"] == "TEST_FUND"
    assert "risk_level" in result
    assert "metrics" in result


def test_api_stress_test():
    result = run_stress_test(
        "TEST_FUND",
        scenarios=["market_crash"],
        positions={"NVDA": 100000.0},
    )
    assert "scenarios_run" in result
    assert "worst_case_loss" in result


def test_api_risk_report():
    result = get_risk_report_api("TEST_FUND")
    assert result["portfolio"] == "TEST_FUND"
    assert "volatility" in result
    assert "var" in result
    assert "exposure" in result


# ========== 8. Edge Cases ==========

def test_empty_returns():
    calc = RiskCalculator()
    result = calc.compute_var([])
    assert result["var_pct"] == 0.0


def test_single_return():
    calc = RiskCalculator()
    result = calc.compute_risk_metrics([0.01])
    assert result["volatility"] == 0.0


def test_zero_volatility():
    vt = VolatilityTargeter()
    result = vt.compute_adjustment(0.0, 1000000.0)
    assert result["scale_factor"] == vt.max_leverage


def test_empty_positions_stress():
    simulator = StressSimulator()
    engine = ScenarioEngine()
    scenario = engine.get_scenario("market_crash")
    result = simulator.simulate(scenario, {})
    assert result.initial_value == 0.0
    assert result.loss_pct == 0.0


print("All tests passed")
