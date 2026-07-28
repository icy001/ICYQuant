"""Tests for AI Risk Intelligence Engine."""

import pytest
from services.risk_intelligence import (
    RiskProfile,
    classify_risk_level,
    compute_risk_score,
    RiskAssessmentEngine,
    RiskPredictionEngine,
    RiskPrediction,
    StressTestEngine,
    StressTestResult,
    ScenarioSimulator,
    Scenario,
    DEFAULT_SCENARIOS,
    RiskExplanationEngine,
    RiskExplanation,
    RiskIntelligenceService,
    # Part 29: Global Risk Intelligence
    SystemicRiskDetector,
    SystemicRiskResult,
    SystemicRiskLevel,
    ContagionChannel,
    ContagionSignal,
    CrisisEarlyWarningSystem,
    CrisisWarningResult,
    CrisisWarning,
    CrisisPhase,
    WarningSeverity,
    WarningType,
    VolatilityRegimePredictor,
    RegimePrediction,
    VolatilityForecast,
    VolatilityRegime,
    RegimeTransition,
    TermStructureState,
    PortfolioDefenseAutomation,
    DefensePlan,
    DefenseAction,
    DefenseLevel,
    DefenseActionType,
    HedgeInstrument,
)


# ====================================================================
# Risk Profile & Utilities
# ====================================================================

class TestRiskProfile:
    def test_create_profile(self):
        p = RiskProfile(portfolio_id="P1", score=50, level="medium")
        assert p.portfolio_id == "P1"
        assert p.score == 50
        assert p.level == "medium"

    def test_to_dict(self):
        p = RiskProfile(
            portfolio_id="P1",
            score=72,
            level="high",
            factor_attribution={"Sector": 45, "Beta": 30},
            risk_drivers=["Sector", "Beta"],
            volatility=0.25,
            concentration=0.4,
        )
        d = p.to_dict()
        assert d["portfolio_id"] == "P1"
        assert d["score"] == 72
        assert d["level"] == "high"
        assert d["factor_attribution"]["Sector"] == 45


class TestClassifyRiskLevel:
    def test_low(self):
        assert classify_risk_level(15) == "low"
        assert classify_risk_level(29) == "low"

    def test_medium(self):
        assert classify_risk_level(30) == "medium"
        assert classify_risk_level(59) == "medium"

    def test_high(self):
        assert classify_risk_level(60) == "high"
        assert classify_risk_level(79) == "high"

    def test_critical(self):
        assert classify_risk_level(80) == "critical"
        assert classify_risk_level(95) == "critical"


class TestComputeRiskScore:
    def test_default_weights(self):
        score = compute_risk_score(
            exposure=0.5, volatility=0.3, drawdown=0.1,
            concentration=0.2, beta=1.0, var_95=0.15,
        )
        assert 0 <= score <= 100

    def test_custom_weights(self):
        score = compute_risk_score(
            exposure=0.8,
            weights={"exposure": 1.0, "volatility": 0.0, "drawdown": 0.0,
                     "concentration": 0.0, "beta": 0.0, "var_95": 0.0},
        )
        assert abs(score - 80.0) < 1e-9

    def test_ceiling(self):
        score = compute_risk_score(
            exposure=2.0, volatility=2.0, drawdown=2.0,
            concentration=2.0, beta=5.0, var_95=2.0,
        )
        assert score <= 100.0


# ====================================================================
# Risk Assessment Engine
# ====================================================================

class TestRiskAssessmentEngine:
    def test_evaluate_simple(self):
        engine = RiskAssessmentEngine()
        result = engine.evaluate_simple(0.5)
        assert result == 50

    def test_evaluate_low_risk(self):
        engine = RiskAssessmentEngine()
        profile = engine.evaluate(
            portfolio_id="P1",
            exposure=0.3, volatility=0.1, drawdown=0.05,
            concentration=0.1, beta=0.5, var_95=0.05,
        )
        assert profile.portfolio_id == "P1"
        assert profile.level == "low"
        assert profile.score < 30

    def test_evaluate_high_risk(self):
        engine = RiskAssessmentEngine()
        profile = engine.evaluate(
            portfolio_id="P2",
            exposure=0.9, volatility=0.7, drawdown=0.3,
            concentration=0.8, beta=2.0, var_95=0.4,
        )
        assert profile.level in ("high", "critical")
        assert profile.score >= 60

    def test_evaluate_custom_factors(self):
        engine = RiskAssessmentEngine()
        profile = engine.evaluate(
            portfolio_id="P3",
            exposure=0.5,
            custom_factors={"Liquidity Risk": 35, "Currency Risk": 25},
        )
        assert "Liquidity Risk" in profile.factor_attribution
        assert "Currency Risk" in profile.factor_attribution

    def test_risk_drivers_always_populated(self):
        engine = RiskAssessmentEngine()
        profile = engine.evaluate(
            portfolio_id="P4",
            exposure=0.1, volatility=0.05, drawdown=0.02,
            concentration=0.05, beta=0.3, var_95=0.02,
        )
        assert len(profile.risk_drivers) >= 1


# ====================================================================
# Risk Prediction Engine
# ====================================================================

class TestRiskPredictionEngine:
    def test_predict_increasing(self):
        engine = RiskPredictionEngine()
        result = engine.predict(
            current_volatility=0.20,
            vol_momentum=0.6,
            correlation_regime=0.5,
            market_stress=0.4,
        )
        assert result.trend == "increasing"
        assert result.predicted_volatility > result.current_volatility
        assert len(result.warnings) > 0

    def test_predict_decreasing(self):
        engine = RiskPredictionEngine()
        result = engine.predict(
            current_volatility=0.30,
            vol_momentum=-0.7,
            correlation_regime=0.0,
            market_stress=0.0,
        )
        assert result.trend == "decreasing"

    def test_predict_stable(self):
        engine = RiskPredictionEngine()
        result = engine.predict(
            current_volatility=0.20,
            vol_momentum=0.0,
            correlation_regime=0.0,
            market_stress=0.0,
        )
        assert result.trend == "stable"

    def test_predict_simple(self):
        engine = RiskPredictionEngine()
        result = engine.predict_simple(0.25)
        assert result["future_risk"] == 0.25

    def test_correlation_warning(self):
        engine = RiskPredictionEngine()
        result = engine.predict(
            current_volatility=0.20,
            correlation_regime=0.8,
        )
        assert any("correlations rising" in w.lower() for w in result.warnings)

    def test_market_stress_warning(self):
        engine = RiskPredictionEngine()
        result = engine.predict(
            current_volatility=0.20,
            market_stress=0.7,
        )
        assert any("tail risk" in w.lower() for w in result.warnings)

    def test_to_dict(self):
        rp = RiskPrediction(
            current_volatility=0.2,
            predicted_volatility=0.35,
            trend="increasing",
            warnings=["risk rising"],
        )
        d = rp.to_dict()
        assert d["predicted_volatility"] == 0.35


# ====================================================================
# Stress Test Engine
# ====================================================================

class TestStressTestEngine:
    def test_run_simple(self):
        engine = StressTestEngine()
        result = engine.run_simple("Market Crash")
        assert result["scenario"] == "Market Crash"
        assert result["loss"] == -0.1

    def test_run_market_crash(self):
        engine = StressTestEngine()
        result = engine.run(
            scenario="Market Crash",
            price_shock=-0.30,
            correlation_amplification=0.5,
            liquidity_discount=0.05,
        )
        assert result.scenario_name == "Market Crash"
        assert result.portfolio_loss < -0.1
        assert result.drawdown < -0.1
        assert result.recovery_time_days > 0
        assert result.passed is False

    def test_run_mild_scenario(self):
        engine = StressTestEngine()
        result = engine.run(
            scenario="Mild Dip",
            price_shock=-0.03,
        )
        assert result.passed is True
        assert result.recovery_time_days <= 5

    def test_run_batch(self):
        engine = StressTestEngine()
        scenarios = [
            {"name": "Crash", "price_shock": -0.30, "correlation_amplification": 0.5},
            {"name": "Mild", "price_shock": -0.03},
        ]
        results = engine.run_batch(scenarios)
        assert len(results) == 2
        assert results[0].scenario_name == "Crash"
        assert results[1].scenario_name == "Mild"

    def test_summary(self):
        engine = StressTestEngine()
        results = [
            StressTestResult("A", -0.1, -0.12, 21, True),
            StressTestResult("B", -0.4, -0.5, 120, False),
            StressTestResult("C", -0.05, -0.06, 5, True),
        ]
        summary = engine.summary(results)
        assert summary["total"] == 3
        assert summary["passed"] == 2
        assert summary["failed"] == 1
        assert summary["worst_scenario"] == "B"

    def test_summary_empty(self):
        engine = StressTestEngine()
        summary = engine.summary([])
        assert summary["total"] == 0

    def test_to_dict(self):
        r = StressTestResult("Test", -0.15, -0.2, 30, False)
        d = r.to_dict()
        assert d["portfolio_loss"] == -0.15
        assert d["passed"] is False


# ====================================================================
# Scenario Simulator
# ====================================================================

class TestScenarioSimulator:
    def test_default_scenarios_exist(self):
        sim = ScenarioSimulator()
        assert len(sim.scenarios) >= 5

    def test_get_scenario(self):
        sim = ScenarioSimulator()
        sc = sim.get_scenario("Market Crash")
        assert sc is not None
        assert sc.category == "market_crash"

    def test_get_scenario_case_insensitive(self):
        sim = ScenarioSimulator()
        sc = sim.get_scenario("market crash")
        assert sc is not None

    def test_get_scenario_not_found(self):
        sim = ScenarioSimulator()
        assert sim.get_scenario("Nonexistent") is None

    def test_by_category(self):
        sim = ScenarioSimulator()
        macro = sim.by_category("macro")
        assert len(macro) >= 1
        assert all(s.category == "macro" for s in macro)

    def test_categories(self):
        sim = ScenarioSimulator()
        cats = sim.categories()
        assert "market_crash" in cats
        assert "macro" in cats

    def test_add_scenario(self):
        sim = ScenarioSimulator()
        sim.add_scenario(Scenario(
            name="Custom Test",
            category="custom",
            description="A test scenario",
            price_shock=-0.05,
        ))
        assert sim.get_scenario("Custom Test") is not None

    def test_simulate_matched(self):
        sim = ScenarioSimulator()
        result = sim.simulate("Market Crash")
        assert result["matched"] is True
        assert "scenario" in result

    def test_simulate_unmatched(self):
        sim = ScenarioSimulator()
        result = sim.simulate("Unknown Event")
        assert result["matched"] is False

    def test_simulate_all(self):
        sim = ScenarioSimulator()
        results = sim.simulate_all()
        assert len(results) == len(sim.scenarios)
        assert all(r["matched"] for r in results)

    def test_to_dict(self):
        sc = Scenario(
            name="Test",
            category="test",
            description="desc",
            price_shock=-0.1,
        )
        d = sc.to_dict()
        assert d["name"] == "Test"
        assert d["price_shock"] == -0.1


# ====================================================================
# Risk Explanation Engine
# ====================================================================

class TestRiskExplanationEngine:
    def test_explain_string(self):
        engine = RiskExplanationEngine()
        result = engine.explain("High sector concentration")
        assert result["reason"] == "High sector concentration"

    def test_explain_profile(self):
        engine = RiskExplanationEngine()
        profile = RiskProfile(
            portfolio_id="P1",
            score=72,
            level="high",
            factor_attribution={"Sector": 45, "Beta": 30, "Currency": 15},
            risk_drivers=["Sector", "Beta"],
            volatility=0.35,
            concentration=0.5,
        )
        result = engine.explain(profile)
        assert "high" in result["reason"].lower()
        assert len(result["factors"]) >= 1
        assert len(result["recommendations"]) >= 1

    def test_explain_dict(self):
        engine = RiskExplanationEngine()
        result = engine.explain({
            "portfolio_id": "P2",
            "score": 50,
            "level": "medium",
        })
        assert "reason" in result

    def test_explain_low_risk(self):
        engine = RiskExplanationEngine()
        profile = RiskProfile(
            portfolio_id="P3",
            score=15,
            level="low",
            volatility=0.1,
            concentration=0.1,
        )
        result = engine.explain(profile)
        assert result["risk_level"] == "low"

    def test_to_dict(self):
        re = RiskExplanation(
            portfolio_id="P1",
            risk_level="high",
            score=72,
            reason="High risk due to sector concentration",
            recommendations=["Reduce exposure"],
        )
        d = re.to_dict()
        assert d["portfolio_id"] == "P1"
        assert d["risk_level"] == "high"


# ====================================================================
# Risk Intelligence Service
# ====================================================================

class TestRiskIntelligenceService:
    def test_assess(self):
        service = RiskIntelligenceService()
        profile = service.assess(
            portfolio_id="P1",
            exposure=0.5,
            volatility=0.3,
            drawdown=0.1,
            concentration=0.2,
            beta=1.0,
            var_95=0.15,
        )
        assert profile.portfolio_id == "P1"
        assert 0 <= profile.score <= 100

    def test_predict(self):
        service = RiskIntelligenceService()
        result = service.predict(
            current_volatility=0.20,
            vol_momentum=0.5,
        )
        assert result.current_volatility == 0.20

    def test_stress_test_scenario(self):
        service = RiskIntelligenceService()
        result = service.stress_test_scenario("Market Crash")
        assert result is not None
        assert result.scenario_name == "Market Crash"

    def test_stress_test_scenario_not_found(self):
        service = RiskIntelligenceService()
        result = service.stress_test_scenario("Nonexistent")
        assert result is None

    def test_stress_test_all(self):
        service = RiskIntelligenceService()
        results = service.stress_test_all()
        assert len(results) == len(service.scenario.scenarios)

    def test_stress_test_summary(self):
        service = RiskIntelligenceService()
        summary = service.stress_test_summary()
        assert "total" in summary
        assert "passed" in summary
        assert "failed" in summary

    def test_explain(self):
        service = RiskIntelligenceService()
        profile = service.assess(
            portfolio_id="P1",
            exposure=0.7,
            volatility=0.5,
            concentration=0.6,
        )
        explanation = service.explain(profile)
        assert explanation.portfolio_id == "P1"

    def test_comprehensive_analysis(self):
        service = RiskIntelligenceService()
        result = service.comprehensive_analysis(
            portfolio_id="P1",
            exposure=0.5,
            volatility=0.25,
            drawdown=0.1,
            concentration=0.3,
            beta=1.2,
            var_95=0.15,
            vol_momentum=0.3,
            correlation_regime=0.4,
            market_stress=0.3,
        )
        assert result["portfolio_id"] == "P1"
        assert "risk_profile" in result
        assert "risk_prediction" in result
        assert "risk_explanation" in result
        assert "stress_test_summary" in result


# ====================================================================
# Integration with DEFAULT_SCENARIOS
# ====================================================================

class TestDefaultScenarios:
    def test_all_have_required_fields(self):
        for sc in DEFAULT_SCENARIOS:
            assert sc.name
            assert sc.category
            assert sc.description
            assert isinstance(sc.price_shock, float)

    def test_categories_cover_risks(self):
        cats = {s.category for s in DEFAULT_SCENARIOS}
        assert "market_crash" in cats
        assert "liquidity" in cats
        assert "volatility" in cats
        assert "macro" in cats


# ====================================================================
# Part 29: Systemic Risk Detector
# ====================================================================

class TestSystemicRiskDetector:
    def test_assess_safe(self):
        detector = SystemicRiskDetector()
        result = detector.assess(
            avg_correlation=0.15, credit_spread=0.8,
            liquidity_stress=0.05, vix=12.0,
            dollar_trend="stable", em_spread=1.5,
        )
        assert result.level == SystemicRiskLevel.SAFE
        assert result.score < 0.2
        assert not result.early_warning

    def test_assess_caution(self):
        detector = SystemicRiskDetector()
        result = detector.assess(
            avg_correlation=0.65, credit_spread=2.8,
            liquidity_stress=0.35, vix=22.0,
            dollar_trend="appreciation", em_spread=3.0,
        )
        assert result.level in (SystemicRiskLevel.CAUTION, SystemicRiskLevel.WATCH)
        assert result.score >= 0.2

    def test_assess_crisis(self):
        detector = SystemicRiskDetector()
        result = detector.assess(
            avg_correlation=0.82, credit_spread=4.5,
            liquidity_stress=0.75, vix=40.0,
            dollar_trend="strong_appreciation", em_spread=6.5,
        )
        assert result.level in (SystemicRiskLevel.CRISIS, SystemicRiskLevel.DANGER)
        assert result.score >= 0.6
        assert result.early_warning

    def test_contagion_signals(self):
        detector = SystemicRiskDetector()
        result = detector.assess(
            avg_correlation=0.75, credit_spread=3.0,
            liquidity_stress=0.55, vix=30.0,
            dollar_trend="strong_appreciation", em_spread=5.0,
        )
        assert len(result.contagion_signals) >= 2

    def test_is_alarming(self):
        safe = SystemicRiskResult(level=SystemicRiskLevel.SAFE, score=0.1)
        assert not safe.is_alarming
        crisis = SystemicRiskResult(level=SystemicRiskLevel.CRISIS, score=0.85)
        assert crisis.is_alarming

    def test_critical_channels(self):
        result = SystemicRiskResult(
            level=SystemicRiskLevel.DANGER, score=0.7,
            contagion_signals=[
                ContagionSignal(
                    channel=ContagionChannel.CORRELATION,
                    severity=0.9, probability=0.8,
                ),
                ContagionSignal(
                    channel=ContagionChannel.CREDIT,
                    severity=0.3, probability=0.4,
                ),
            ],
        )
        critical = result.critical_channels
        assert len(critical) == 1
        assert critical[0].channel == ContagionChannel.CORRELATION

    def test_defense_multiplier(self):
        result = SystemicRiskResult(level=SystemicRiskLevel.DANGER, score=0.8)
        assert result.defense_multiplier <= 0.3

    def test_contagion_paths(self):
        detector = SystemicRiskDetector()
        paths = detector.get_contagion_paths("equities")
        assert len(paths) >= 2
        assert "credit" in paths

    def test_vulnerable_assets(self):
        detector = SystemicRiskDetector()
        assets = detector.get_vulnerable_assets("USD")
        assert "emerging_markets" in assets

    def test_dimensions_populated(self):
        detector = SystemicRiskDetector()
        result = detector.assess(
            avg_correlation=0.3, credit_spread=1.5,
            liquidity_stress=0.2, vix=18.0,
        )
        assert result.correlation_risk > 0
        assert result.credit_risk > 0
        assert result.liquidity_risk > 0
        assert result.currency_risk > 0

    def test_history_tracking(self):
        detector = SystemicRiskDetector()
        for _ in range(10):
            detector.assess(vix=15.0)
        assert len(detector.vix_history) == 10

    def test_clear(self):
        detector = SystemicRiskDetector()
        detector.assess(vix=20.0)
        detector.clear()
        assert len(detector.vix_history) == 0

    def test_contagion_signal_properties(self):
        sig = ContagionSignal(severity=0.8, probability=0.7)
        assert abs(sig.risk_score - 0.56) < 1e-9
        assert sig.is_critical


# ====================================================================
# Part 29: Crisis Early Warning System
# ====================================================================

class TestCrisisEarlyWarningSystem:
    def test_analyze_normal(self):
        system = CrisisEarlyWarningSystem()
        result = system.analyze(
            vix=12.0, vix_change=0.0, avg_correlation=0.1,
            credit_spread=0.5, liquidity_stress=0.05,
            safe_haven_demand=0.0, market_breadth=0.6,
        )
        assert result.current_phase == CrisisPhase.NORMAL
        assert result.composite_alert < 0.2
        assert not result.should_defend

    def test_analyze_buildup(self):
        system = CrisisEarlyWarningSystem()
        result = system.analyze(
            vix=26.0, vix_change=0.05, avg_correlation=0.4,
            credit_spread=1.8, liquidity_stress=0.25,
            safe_haven_demand=0.35, market_breadth=0.4,
        )
        assert result.composite_alert >= 0.2
        assert len(result.active_warnings) >= 1

    def test_analyze_crisis(self):
        system = CrisisEarlyWarningSystem()
        result = system.analyze(
            vix=38.0, vix_change=0.2, avg_correlation=0.88,
            credit_spread=3.2, credit_change=0.3,
            liquidity_stress=0.75, safe_haven_demand=0.85,
            market_breadth=0.15,
        )
        assert result.composite_alert >= 0.5
        assert result.current_phase in (CrisisPhase.PRECURSOR, CrisisPhase.TRIGGER)
        assert result.should_defend

    def test_volatility_breakout_critical(self):
        system = CrisisEarlyWarningSystem()
        result = system.analyze(vix=40.0)
        assert len(result.warnings) >= 1
        assert result.warnings[0].severity == WarningSeverity.CRITICAL

    def test_correlation_spike(self):
        system = CrisisEarlyWarningSystem()
        result = system.analyze(avg_correlation=0.9)
        assert any(w.warning_type == WarningType.CORRELATION_SPIKE
                   for w in result.warnings)

    def test_liquidity_freeze(self):
        system = CrisisEarlyWarningSystem()
        result = system.analyze(liquidity_stress=0.8)
        assert any(w.warning_type == WarningType.LIQUIDITY_FREEZE
                   for w in result.warnings)

    def test_safe_haven_surge(self):
        system = CrisisEarlyWarningSystem()
        result = system.analyze(safe_haven_demand=0.9)
        assert any(w.warning_type == WarningType.SAFE_HAVEN_SURGE
                   for w in result.warnings)

    def test_momentum_crash(self):
        system = CrisisEarlyWarningSystem()
        result = system.analyze(market_breadth=0.1)
        assert any(w.warning_type == WarningType.MOMENTUM_CRASH
                   for w in result.warnings)

    def test_urgent_warnings(self):
        system = CrisisEarlyWarningSystem()
        result = system.analyze(
            vix=40.0, liquidity_stress=0.8,
            avg_correlation=0.9, market_breadth=0.1,
        )
        assert len(result.urgent_warnings) >= 3

    def test_defense_level(self):
        result = CrisisWarningResult(composite_alert=0.3)
        assert result.defense_level == 0.0
        result2 = CrisisWarningResult(composite_alert=0.65)
        assert result2.defense_level == 0.6
        result3 = CrisisWarningResult(composite_alert=0.85)
        assert result3.defense_level == 0.9

    def test_quick_scan(self):
        system = CrisisEarlyWarningSystem()
        scan = system.quick_scan(vix=30.0, credit_spread=3.0)
        assert scan["has_warnings"]
        assert scan["vix_alert"]
        assert scan["credit_alert"]

    def test_clear(self):
        system = CrisisEarlyWarningSystem()
        system.analyze(vix=25.0)
        system.clear()
        assert system._warning_counter == 0

    def test_crisis_warning_properties(self):
        warning = CrisisWarning(
            warning_type=WarningType.VOLATILITY_BREAKOUT,
            severity=WarningSeverity.CRITICAL,
            confidence=0.85,
        )
        assert warning.is_urgent
        assert warning.is_actionable


# ====================================================================
# Part 29: Volatility Regime Predictor
# ====================================================================

class TestVolatilityRegimePredictor:
    def test_predict_normal(self):
        predictor = VolatilityRegimePredictor()
        result = predictor.predict(
            current_vol=0.12, vix=14.0,
            vix_1m=15.5, vix_3m=17.0, vix_6m=18.5,
        )
        assert result.current_regime in (
            VolatilityRegime.LOW_VOL, VolatilityRegime.NORMAL,
        )
        assert result.forecast is not None

    def test_predict_elevated(self):
        predictor = VolatilityRegimePredictor()
        result = predictor.predict(
            current_vol=0.22, vix=26.0,
            vix_1m=25.0, vix_3m=24.0, vix_6m=23.0,
        )
        assert result.current_regime == VolatilityRegime.ELEVATED

    def test_predict_extreme(self):
        predictor = VolatilityRegimePredictor()
        result = predictor.predict(
            current_vol=0.55, vix=52.0,
            vix_1m=40.0, vix_3m=36.0, vix_6m=33.0,
        )
        assert result.current_regime == VolatilityRegime.EXTREME

    def test_term_structure_contango(self):
        predictor = VolatilityRegimePredictor()
        result = predictor.predict(
            current_vol=0.12, vix=14.0,
            vix_1m=15.0, vix_3m=18.0, vix_6m=20.0,
        )
        assert result.forecast is not None
        assert result.forecast.term_structure == TermStructureState.CONTANGO

    def test_term_structure_backwardation(self):
        predictor = VolatilityRegimePredictor()
        result = predictor.predict(
            current_vol=0.22, vix=24.0,
            vix_1m=22.0, vix_3m=21.0, vix_6m=20.0,
        )
        assert result.forecast is not None
        assert result.forecast.term_structure == TermStructureState.BACKWARDATION

    def test_regime_probabilities(self):
        predictor = VolatilityRegimePredictor()
        result = predictor.predict(
            current_vol=0.15, vix=15.0,
            vix_1m=16.0, vix_3m=18.0, vix_6m=19.0,
        )
        assert result.forecast is not None
        probs = result.forecast.regime_probabilities
        assert len(probs) >= 3
        total = sum(probs.values())
        assert abs(total - 1.0) < 0.05

    def test_dominant_regime(self):
        predictor = VolatilityRegimePredictor()
        result = predictor.predict(
            current_vol=0.12, vix=13.0,
            vix_1m=14.0, vix_3m=16.0, vix_6m=17.0,
        )
        assert result.forecast is not None
        dominant = result.forecast.dominant_regime
        assert dominant in ("low_vol", "normal")

    def test_transition_stable(self):
        predictor = VolatilityRegimePredictor()
        result = predictor.predict(
            current_vol=0.12, vix=14.0,
            vix_1m=15.0, vix_3m=17.0, vix_6m=18.0,
        )
        assert result.transition == RegimeTransition.STABLE

    def test_transition_heating(self):
        predictor = VolatilityRegimePredictor()
        result = predictor.predict(
            current_vol=0.25, vix=24.0,
            vix_1m=23.0, vix_3m=22.0, vix_6m=21.0,
            vol_of_vol=0.4,
        )
        assert result.transition in (
            RegimeTransition.HEATING, RegimeTransition.STABLE,
        )

    def test_is_heating_up(self):
        result = RegimePrediction(
            current_regime=VolatilityRegime.NORMAL,
            predicted_regime=VolatilityRegime.ELEVATED,
            transition=RegimeTransition.HEATING,
        )
        assert result.is_heating_up

    def test_requires_defense(self):
        result = RegimePrediction(
            predicted_regime=VolatilityRegime.HIGH_VOL,
        )
        assert result.requires_defense

    def test_quick_scan(self):
        predictor = VolatilityRegimePredictor()
        scan = predictor.quick_scan(52.0)
        assert scan["is_stressed"]
        assert scan["regime"] == "extreme"

    def test_clear(self):
        predictor = VolatilityRegimePredictor()
        predictor.predict(current_vol=0.15, vix=15.0)
        predictor.clear()
        assert len(predictor.vix_history) == 0

    def test_forecast_trend(self):
        forecast = VolatilityForecast(
            current_vol=0.15,
            forecast_21d=0.22,
        )
        assert forecast.trend == "increasing"

    def test_regime_shift_probability(self):
        predictor = VolatilityRegimePredictor()
        result = predictor.predict(
            current_vol=0.18, vix=20.0, vol_of_vol=0.6,
            vix_1m=16.0, vix_3m=15.0, vix_6m=14.0,
        )
        assert result.regime_shift_probability >= 0.1


# ====================================================================
# Part 29: Portfolio Defense Automation
# ====================================================================

class TestPortfolioDefenseAutomation:
    def test_generate_plan_no_defense(self):
        defense = PortfolioDefenseAutomation()
        plan = defense.generate_plan(
            systemic_risk_score=0.05,
            crisis_alert=0.05,
            volatility_regime="low_vol",
        )
        assert plan.defense_level == DefenseLevel.NONE
        assert not plan.is_defensive

    def test_generate_plan_light_defense(self):
        defense = PortfolioDefenseAutomation()
        plan = defense.generate_plan(
            systemic_risk_score=0.35,
            crisis_alert=0.25,
            volatility_regime="elevated",
        )
        assert plan.defense_level == DefenseLevel.LIGHT
        assert plan.is_defensive

    def test_generate_plan_moderate_defense(self):
        defense = PortfolioDefenseAutomation()
        plan = defense.generate_plan(
            systemic_risk_score=0.55,
            crisis_alert=0.4,
            volatility_regime="elevated",
            current_drawdown=0.12,
        )
        assert plan.defense_level == DefenseLevel.MODERATE

    def test_generate_plan_heavy_defense(self):
        defense = PortfolioDefenseAutomation()
        plan = defense.generate_plan(
            systemic_risk_score=0.65,
            crisis_alert=0.6,
            volatility_regime="high_vol",
            current_drawdown=0.18,
            concentration=0.7,
        )
        assert plan.defense_level in (DefenseLevel.HEAVY, DefenseLevel.FULL)

    def test_generate_plan_full_defense(self):
        defense = PortfolioDefenseAutomation()
        plan = defense.generate_plan(
            systemic_risk_score=0.85,
            crisis_alert=0.85,
            volatility_regime="tail",
            current_drawdown=0.25,
            current_leverage=2.0,
        )
        assert plan.defense_level == DefenseLevel.FULL

    def test_actions_sorted_by_priority(self):
        defense = PortfolioDefenseAutomation()
        plan = defense.generate_plan(
            systemic_risk_score=0.5,
            crisis_alert=0.4,
            volatility_regime="high_vol",
            current_drawdown=0.15,
            current_leverage=2.0,
            positions={"TECH": 0.25},
        )
        sorted_actions = plan.sorted_actions()
        for i in range(len(sorted_actions) - 1):
            assert sorted_actions[i].priority <= sorted_actions[i+1].priority

    def test_leverage_reduction_action(self):
        defense = PortfolioDefenseAutomation()
        plan = defense.generate_plan(
            systemic_risk_score=0.6,
            crisis_alert=0.5,
            volatility_regime="high_vol",
            current_leverage=2.5,
        )
        leverage_actions = [
            a for a in plan.actions
            if a.action_type == DefenseActionType.REDUCE_LEVERAGE
        ]
        assert len(leverage_actions) >= 1

    def test_drawdown_stop_action(self):
        defense = PortfolioDefenseAutomation()
        plan = defense.generate_plan(
            systemic_risk_score=0.4,
            crisis_alert=0.3,
            volatility_regime="elevated",
            current_drawdown=0.22,
        )
        stop_actions = [
            a for a in plan.actions
            if a.action_type in (DefenseActionType.STOP_LOSS,
                                 DefenseActionType.TRAILING_STOP)
        ]
        assert len(stop_actions) >= 1

    def test_hedge_actions_for_scenarios(self):
        defense = PortfolioDefenseAutomation()
        plan = defense.generate_plan(
            systemic_risk_score=0.6,
            crisis_alert=0.55,
            volatility_regime="high_vol",
            risk_scenarios=["volatility_spike", "correlation_crisis"],
        )
        hedge_actions = [
            a for a in plan.actions
            if a.action_type == DefenseActionType.ADD_HEDGE
        ]
        assert len(hedge_actions) >= 1

    def test_position_limit_action(self):
        defense = PortfolioDefenseAutomation()
        plan = defense.generate_plan(
            systemic_risk_score=0.5,
            crisis_alert=0.4,
            volatility_regime="elevated",
            positions={"MEGA_CAP": 0.4},
        )
        limit_actions = [
            a for a in plan.actions
            if a.action_type == DefenseActionType.POSITION_LIMIT
        ]
        assert len(limit_actions) >= 1

    def test_correlation_defense(self):
        defense = PortfolioDefenseAutomation()
        plan = defense.generate_plan(
            systemic_risk_score=0.6,
            crisis_alert=0.5,
            volatility_regime="high_vol",
            correlations={"TECH": 0.85, "FIN": 0.92},
        )
        corr_actions = [
            a for a in plan.actions
            if a.action_type == DefenseActionType.CORRELATION_HEDGE
        ]
        assert len(corr_actions) >= 1

    def test_critical_actions(self):
        defense = PortfolioDefenseAutomation()
        plan = defense.generate_plan(
            systemic_risk_score=0.8,
            crisis_alert=0.7,
            volatility_regime="extreme",
            current_drawdown=0.2,
            current_leverage=3.0,
        )
        assert len(plan.critical_actions) >= 1

    def test_total_allocation_change(self):
        defense = PortfolioDefenseAutomation()
        plan = defense.generate_plan(
            systemic_risk_score=0.6,
            crisis_alert=0.5,
            volatility_regime="high_vol",
            current_leverage=2.0,
            positions={"STOCK": 0.3},
        )
        assert plan.total_allocation_change >= 0

    def test_quick_defense_check(self):
        defense = PortfolioDefenseAutomation()
        check = defense.quick_defense_check(
            systemic_risk=0.7, crisis_alert=0.6,
            vol_regime="extreme", drawdown=0.2,
        )
        assert check["needs_defense"]
        assert check["hedge_budget"] > 0

    def test_defense_action_properties(self):
        action = DefenseAction(
            current_allocation=0.3, target_allocation=0.15,
            priority=1,
        )
        assert action.delta_bps == 1500
        assert action.is_critical

    def test_defense_plan_has_description(self):
        defense = PortfolioDefenseAutomation()
        plan = defense.generate_plan(
            systemic_risk_score=0.5,
            crisis_alert=0.4,
            volatility_regime="high_vol",
        )
        assert len(plan.description) > 0

    def test_hedge_map_coverage(self):
        defense = PortfolioDefenseAutomation()
        scenarios = [
            "volatility_spike", "correlation_crisis", "liquidity_freeze",
            "credit_stress", "dollar_surge", "em_crisis",
            "safe_haven_rush", "momentum_crash", "tail_risk",
        ]
        for sc in scenarios:
            insts = defense.HEDGE_MAP.get(sc, [])
            assert len(insts) >= 1, f"No hedge instruments for {sc}"


# ====================================================================
# Part 29: Service Integration
# ====================================================================

class TestGlobalRiskIntelligenceService:
    def test_detect_systemic_risk(self):
        service = RiskIntelligenceService()
        result = service.detect_systemic_risk(
            avg_correlation=0.3, credit_spread=1.5,
            liquidity_stress=0.2, vix=18.0,
        )
        assert isinstance(result, SystemicRiskResult)

    def test_analyze_crisis_warning(self):
        service = RiskIntelligenceService()
        result = service.analyze_crisis_warning(
            vix=20.0, avg_correlation=0.4,
        )
        assert isinstance(result, CrisisWarningResult)

    def test_predict_volatility_regime(self):
        service = RiskIntelligenceService()
        result = service.predict_volatility_regime(
            current_vol=0.15, vix=15.0,
            vix_1m=16.0, vix_3m=18.0,
        )
        assert isinstance(result, RegimePrediction)

    def test_generate_defense_plan(self):
        service = RiskIntelligenceService()
        plan = service.generate_defense_plan(
            systemic_risk_score=0.3,
            crisis_alert=0.3,
            volatility_regime="elevated",
        )
        assert isinstance(plan, DefensePlan)

    def test_comprehensive_analysis_with_new_engines(self):
        service = RiskIntelligenceService()
        result = service.comprehensive_analysis(
            portfolio_id="P1",
            exposure=0.5,
            volatility=0.2,
            drawdown=0.1,
            concentration=0.3,
            beta=1.2,
            var_95=0.15,
            vol_momentum=0.3,
            correlation_regime=0.3,
            market_stress=0.3,
        )
        assert "systemic_risk" in result
        assert "crisis_warning" in result
        assert "volatility_regime" in result
        assert "defense_plan" in result
        assert result["portfolio_id"] == "P1"

    def test_global_risk_scan(self):
        service = RiskIntelligenceService()
        scan = service.global_risk_scan(
            vix=15.0, credit_spread=1.0,
            avg_correlation=0.2, liquidity_stress=0.1,
            dollar_trend="stable", em_spread=2.0,
            safe_haven_demand=0.0, market_breadth=0.5,
        )
        assert "aggregate_risk_score" in scan
        assert "systemic_risk" in scan
        assert "crisis_warning" in scan
        assert "volatility_regime" in scan
        assert "defense_plan" in scan
        assert "summary" in scan
        assert 0.0 <= scan["aggregate_risk_score"] <= 1.0

    def test_global_risk_scan_crisis(self):
        service = RiskIntelligenceService()
        scan = service.global_risk_scan(
            vix=38.0, credit_spread=3.2,
            avg_correlation=0.85, liquidity_stress=0.7,
            dollar_trend="strong_appreciation", em_spread=5.5,
            safe_haven_demand=0.85, market_breadth=0.15,
        )
        assert scan["aggregate_risk_score"] >= 0.3

    def test_contagion_paths_service(self):
        service = RiskIntelligenceService()
        paths = service.get_contagion_paths("equities")
        assert len(paths) >= 2

    def test_quick_crisis_scan(self):
        service = RiskIntelligenceService()
        scan = service.quick_crisis_scan(vix=30.0, credit_spread=3.0)
        assert scan["has_warnings"]

    def test_quick_regime_scan(self):
        service = RiskIntelligenceService()
        scan = service.quick_regime_scan(vix=14.0)
        assert "regime" in scan

    def test_quick_defense_check(self):
        service = RiskIntelligenceService()
        check = service.quick_defense_check(
            systemic_risk=0.6, crisis_alert=0.5,
            vol_regime="high_vol", drawdown=0.15,
        )
        assert check["needs_defense"]
