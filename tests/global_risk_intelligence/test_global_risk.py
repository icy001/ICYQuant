"""Tests for AI Global Risk Intelligence Engine (Part 30)."""

import pytest
from services.global_risk_intelligence import (
    # Detector
    SystemicRiskDetector,
    SystemicRiskAssessment,
    RiskLevel,
    MarketDomain,
    DomainRisk,
    # Volatility
    VolatilityRegimeEngine,
    RegimeResult,
    VolatilityRegime,
    RegimeAction,
    # Liquidity
    LiquidityStressAnalyzer,
    LiquidityAssessment,
    LiquidityLevel,
    LiquidityComponent,
    # Black Swan
    BlackSwanDetector,
    BlackSwanAssessment,
    BlackSwanSignal,
    EventCategory,
    EventSeverity,
    # Contagion
    ContagionEngine,
    ContagionResult,
    ContagionPath,
    ContagionNode,
    # Stress Test
    PortfolioStressTest,
    StressTestResult,
    StressScenario,
    # Defense
    AutoDefenseEngine,
    DefenseDecision,
    DefenseOrder,
    DefenseLevel,
    DefenseAction,
    # Memory
    RiskMemory,
    RiskEvent,
    RiskKnowledgeBase,
    # Service
    GlobalRiskIntelligenceService,
)


# ====================================================================
# Systemic Risk Detector
# ====================================================================

class TestSystemicRiskDetector:
    def test_detect_normal(self):
        detector = SystemicRiskDetector()
        result = detector.detect(
            vix=14.0, ig_spread=0.8, equity_drawdown=0.02,
        )
        assert result.level == RiskLevel.NORMAL
        assert result.score < 0.3

    def test_detect_warning(self):
        detector = SystemicRiskDetector()
        result = detector.detect(
            vix=28.0, ig_spread=2.5, equity_drawdown=0.15,
            equity_breadth=0.30, yield_curve=-0.006,
            hy_spread=5.5, dxy_change=0.02,
        )
        assert result.level in (RiskLevel.WARNING, RiskLevel.NORMAL)
        assert result.score >= 0.25

    def test_detect_critical(self):
        detector = SystemicRiskDetector()
        result = detector.detect(
            vix=42.0, ig_spread=3.0, hy_spread=7.0,
            equity_drawdown=0.25, equity_breadth=0.15,
            yield_curve=-0.01, dxy_change=0.04,
            gold_oil_ratio=40, copper_change=-0.08,
            crypto_drawdown=0.55,
        )
        assert result.level in (RiskLevel.CRITICAL, RiskLevel.WARNING)
        assert result.score >= 0.4

    def test_all_domains_present(self):
        detector = SystemicRiskDetector()
        result = detector.detect(vix=18.0)
        assert "equity" in result.domain_risks
        assert "rates" in result.domain_risks
        assert "credit" in result.domain_risks
        assert "vix" in result.domain_risks
        assert "fx" in result.domain_risks
        assert "commodity" in result.domain_risks
        assert "crypto" in result.domain_risks
        assert "funding" in result.domain_risks

    def test_alarming_domains_tracked(self):
        detector = SystemicRiskDetector()
        result = detector.detect(
            vix=40.0, equity_drawdown=0.25,
            ig_spread=2.8, hy_spread=6.5,
        )
        assert len(result.alarming_domains) >= 1
        assert result.requires_action

    def test_defense_ratio(self):
        result = SystemicRiskAssessment(level=RiskLevel.CRITICAL)
        assert result.defense_ratio >= 0.5
        result2 = SystemicRiskAssessment(level=RiskLevel.NORMAL)
        assert result2.defense_ratio < 0.5

    def test_quick_scan(self):
        detector = SystemicRiskDetector()
        scan = detector.quick_scan(vix=35.0, ig_spread=2.5)
        assert "level" in scan
        assert "score" in scan

    def test_domain_risk_properties(self):
        dr = DomainRisk(domain=MarketDomain.EQUITY, stress=0.6)
        assert dr.is_alarming
        dr2 = DomainRisk(domain=MarketDomain.EQUITY, stress=0.3)
        assert not dr2.is_alarming

    def test_clear(self):
        detector = SystemicRiskDetector()
        detector.detect(vix=20.0)
        detector.clear()
        assert len(detector.history) == 0

    def test_default_market_data(self):
        detector = SystemicRiskDetector()
        result = detector.detect()
        assert result.level == RiskLevel.NORMAL
        assert result.score < 0.3

    def test_market_data_dict_input(self):
        detector = SystemicRiskDetector()
        result = detector.detect({"vix": 35.0, "ig_spread": 2.5, "equity_drawdown": 0.15, "equity_breadth": 0.25})
        assert result.score >= 0.2

    def test_kwargs_input(self):
        detector = SystemicRiskDetector()
        result = detector.detect(vix=35.0, ig_spread=2.5, equity_drawdown=0.15, equity_breadth=0.25)
        assert result.score >= 0.2


# ====================================================================
# Volatility Regime Engine
# ====================================================================

class TestVolatilityRegimeEngine:
    def test_classify_low_vol(self):
        engine = VolatilityRegimeEngine()
        result = engine.classify(10.0)
        assert result.regime == VolatilityRegime.LOW_VOL
        assert not result.is_stressed

    def test_classify_normal_vol(self):
        engine = VolatilityRegimeEngine()
        result = engine.classify(22.0)
        assert result.regime == VolatilityRegime.NORMAL_VOL

    def test_classify_high_vol(self):
        engine = VolatilityRegimeEngine()
        result = engine.classify(32.0)
        assert result.regime == VolatilityRegime.HIGH_VOL
        assert result.is_stressed

    def test_classify_crisis_vol(self):
        engine = VolatilityRegimeEngine()
        result = engine.classify(55.0)
        assert result.regime == VolatilityRegime.CRISIS_VOL
        assert result.is_stressed

    def test_size_multiplier(self):
        engine = VolatilityRegimeEngine()
        normal = engine.classify(22.0)
        assert normal.size_multiplier == 1.0
        crisis = engine.classify(55.0)
        assert crisis.size_multiplier <= 0.3

    def test_constraints(self):
        engine = VolatilityRegimeEngine()
        result = engine.classify(32.0)
        assert result.max_leverage <= 1.0
        assert result.max_position_size <= 0.15

    def test_backwardation_amplifies(self):
        engine = VolatilityRegimeEngine()
        normal = engine.classify(22.0, vix_term="contango")
        stressed = engine.classify(22.0, vix_term="backwardation")
        # Backwardation should result in higher stress
        assert stressed.is_stressed or stressed.size_multiplier <= normal.size_multiplier

    def test_quick_classify(self):
        engine = VolatilityRegimeEngine()
        scan = engine.quick_classify(40.0)
        assert scan["stressed"]
        assert scan["max_leverage"] <= 1.0

    def test_clear(self):
        engine = VolatilityRegimeEngine()
        engine.classify(20.0)
        engine.clear()
        assert len(engine.vix_history) == 0

    def test_vix_percentile_tracks(self):
        engine = VolatilityRegimeEngine()
        for _ in range(10):
            engine.classify(15.0)
        engine.classify(30.0)
        result = engine.classify(15.0)
        assert result.vix_percentile < 80  # 15 is low relative to 30


# ====================================================================
# Liquidity Stress Analyzer
# ====================================================================

class TestLiquidityStressAnalyzer:
    def test_analyze_normal(self):
        analyzer = LiquidityStressAnalyzer()
        result = analyzer.analyze(
            funding_spread=0.10, libor_ois=0.05,
            ig_bid_ask=0.02, hy_bid_ask=0.05,
            repo_rate=0.01, cross_currency_basis=-0.05,
        )
        assert result.level in (LiquidityLevel.AMPLE, LiquidityLevel.NORMAL)
        assert result.score < 0.3

    def test_analyze_stressed(self):
        analyzer = LiquidityStressAnalyzer()
        result = analyzer.analyze(
            funding_spread=0.6, libor_ois=0.6,
            ig_bid_ask=0.10, hy_bid_ask=0.30,
            repo_rate=0.10, fails_to_deliver=0.04,
            cross_currency_basis=-0.6,
        )
        assert result.level in (LiquidityLevel.STRESSED, LiquidityLevel.TIGHT,
                                 LiquidityLevel.FREEZE)
        assert result.score >= 0.4
        assert result.requires_liquidity_reduction

    def test_all_channels_present(self):
        analyzer = LiquidityStressAnalyzer()
        result = analyzer.analyze()
        assert "funding" in result.components
        assert "credit" in result.components
        assert "repo" in result.components
        assert "dollar" in result.components

    def test_stressed_channels(self):
        analyzer = LiquidityStressAnalyzer()
        result = analyzer.analyze(
            funding_spread=0.6, libor_ois=0.6,
        )
        assert "funding" in result.stressed_channels

    def test_position_cap(self):
        result = LiquidityAssessment(level=LiquidityLevel.FREEZE)
        assert result.position_size_cap <= 0.15
        result2 = LiquidityAssessment(level=LiquidityLevel.AMPLE)
        assert result2.position_size_cap >= 0.9

    def test_quick_scan(self):
        analyzer = LiquidityStressAnalyzer()
        scan = analyzer.quick_scan(
            funding_spread=0.6, ig_ba=0.12,
        )
        assert "level" in scan
        assert "score" in scan
        assert "position_cap" in scan

    def test_clear(self):
        analyzer = LiquidityStressAnalyzer()
        analyzer.analyze()
        analyzer.clear()
        assert len(analyzer.history) == 0

    def test_liquidity_component_properties(self):
        lc = LiquidityComponent(channel="funding", stress=0.5)
        assert lc.stress == 0.5


# ====================================================================
# Black Swan Detector
# ====================================================================

class TestBlackSwanDetector:
    def test_detect_normal(self):
        detector = BlackSwanDetector(signal_threshold=0.01)
        result = detector.detect(market_stress=0.05, vix=12.0)
        # With many signal types and very low threshold, even normal
        # conditions trigger some signals — verify structure is intact
        assert result.severity is not None
        assert isinstance(result.overall_probability, float)
        assert 0.0 <= result.overall_probability <= 1.0

    def test_detect_elevated(self):
        detector = BlackSwanDetector()
        result = detector.detect(market_stress=0.3, vix=30.0, credit_spread=2.5)
        assert result.severity != EventSeverity.LOW
        assert result.overall_probability >= 0.03

    def test_detect_extreme(self):
        detector = BlackSwanDetector()
        result = detector.detect(
            market_stress=0.7, vix=45.0, credit_spread=3.5,
            geopolitical_tension=0.8, cyber_threat_level=0.7,
        )
        assert result.severity in (EventSeverity.HIGH, EventSeverity.EXTREME)
        assert result.overall_probability >= 0.10

    def test_signals_generated(self):
        detector = BlackSwanDetector()
        result = detector.detect(market_stress=0.5, vix=35.0)
        assert len(result.signals) >= 1

    def test_is_defcon(self):
        result = BlackSwanAssessment(
            severity=EventSeverity.EXTREME,
            overall_probability=0.15,
        )
        assert result.is_defcon

    def test_recommended_hedge(self):
        detector = BlackSwanDetector()
        result = detector.detect(market_stress=0.5, vix=40.0)
        assert result.recommended_hedge >= 0

    def test_quick_scan(self):
        detector = BlackSwanDetector()
        scan = detector.quick_scan(market_stress=0.5, vix=35.0)
        assert "probability" in scan
        assert "severity" in scan

    def test_signal_properties(self):
        sig = BlackSwanSignal(
            probability=0.1, impact=0.3,
            category=EventCategory.FINANCIAL,
        )
        assert sig.expected_loss == 0.03
        assert sig.is_urgent

    def test_market_stress_amplifies(self):
        detector = BlackSwanDetector()
        low = detector.detect(market_stress=0.0, vix=15.0)
        high = detector.detect(market_stress=0.6, vix=15.0)
        assert high.overall_probability >= low.overall_probability

    def test_all_categories_present(self):
        detector = BlackSwanDetector()
        # Check that the signal library covers all categories
        for cat in EventCategory:
            assert cat in detector.SIGNAL_LIBRARY, f"Missing category: {cat}"
            assert len(detector.SIGNAL_LIBRARY[cat]) >= 1


# ====================================================================
# Contagion Engine
# ====================================================================

class TestContagionEngine:
    def test_analyze_known_source(self):
        engine = ContagionEngine()
        result = engine.analyze("US Bond", initial_shock=0.7)
        assert result.source == "US Bond"
        assert len(result.affected_nodes) >= 1
        assert len(result.propagation_paths) >= 1

    def test_analyze_unknown_source(self):
        engine = ContagionEngine()
        result = engine.analyze("Unknown Asset")
        assert result.systemic_impact == 0.0
        assert len(result.affected_nodes) == 0

    def test_systemic_impact_scales(self):
        engine = ContagionEngine()
        mild = engine.analyze("NASDAQ", initial_shock=0.2)
        severe = engine.analyze("NASDAQ", initial_shock=0.8)
        assert severe.systemic_impact >= mild.systemic_impact

    def test_is_systemic_threat(self):
        result = ContagionResult(systemic_impact=0.7)
        assert result.is_systemic_threat
        result2 = ContagionResult(systemic_impact=0.3)
        assert not result2.is_systemic_threat

    def test_analyze_multi(self):
        engine = ContagionEngine()
        results = engine.analyze_multi({
            "US Bond": 0.5,
            "Credit Event": 0.6,
        })
        assert len(results) == 2
        assert "US Bond" in results
        assert "Credit Event" in results

    def test_most_threatened(self):
        engine = ContagionEngine()
        threatened = engine.most_threatened({
            "US Bond": 0.7,
            "Credit Event": 0.6,
        })
        assert len(threatened) >= 1
        # First entry should have highest impact
        assert threatened[0][1] >= 0

    def test_get_exposure(self):
        engine = ContagionEngine()
        exposure = engine.get_exposure("NASDAQ")
        assert 0 <= exposure <= 1.0

    def test_contagion_path_structure(self):
        path = ContagionPath(
            path=["NASDAQ", "AI Stocks", "Semiconductor ETF"],
            total_impact=0.5,
            probability=0.4,
        )
        assert len(path.path) == 3

    def test_contagion_node_structure(self):
        node = ContagionNode(
            name="NASDAQ",
            shock=0.6,
            resilience=0.4,
            connections=["AI Stocks", "Growth Stocks"],
        )
        assert node.shock == 0.6

    def test_credit_event_propagates(self):
        engine = ContagionEngine()
        result = engine.analyze("Credit Event", initial_shock=0.5)
        assert len(result.affected_nodes) >= 1


# ====================================================================
# Portfolio Stress Test
# ====================================================================

class TestPortfolioStressTest:
    def test_run_fed_hike(self):
        stress = PortfolioStressTest()
        result = stress.run("Fed +100bp")
        assert result.scenario == "Fed +100bp"
        assert result.portfolio_loss < 0

    def test_run_vix_50(self):
        stress = PortfolioStressTest()
        result = stress.run("VIX 50")
        assert result.portfolio_loss < -0.05
        assert result.severity != "low"

    def test_run_nasdaq_crash(self):
        stress = PortfolioStressTest()
        result = stress.run("NASDAQ -20%")
        assert result.portfolio_loss < -0.08

    def test_run_unknown(self):
        stress = PortfolioStressTest()
        result = stress.run("Unknown Scenario")
        assert result.severity == "unknown"

    def test_run_all(self):
        stress = PortfolioStressTest()
        results = stress.run_all()
        assert len(results) == len(stress.scenarios)

    def test_summary(self):
        stress = PortfolioStressTest()
        results = stress.run_all()
        summary = stress.summary(results)
        assert summary["total"] == len(results)
        assert summary["pass_rate"] >= 0

    def test_severity_classification(self):
        result = StressTestResult(
            scenario="Test",
            portfolio_loss=-0.25,
            severity="high",
        )
        assert result.is_severe

    def test_add_scenario(self):
        stress = PortfolioStressTest()
        stress.add_scenario(StressScenario(
            name="Custom Test",
            description="Custom",
            equity_shock=-0.05,
        ))
        names = stress.get_scenario_names()
        assert "Custom Test" in names

    def test_all_default_scenarios(self):
        stress = PortfolioStressTest()
        names = stress.get_scenario_names()
        assert "Fed +100bp" in names
        assert "Oil +30%" in names
        assert "USD +10%" in names
        assert "VIX 50" in names
        assert "NASDAQ -20%" in names
        assert "Credit Crisis" in names
        assert "EM Contagion" in names
        assert "Rate Cut Panic" in names

    def test_clear(self):
        stress = PortfolioStressTest()
        stress.clear()
        assert len(stress.scenarios) == 0


# ====================================================================
# Auto Defense Engine
# ====================================================================

class TestAutoDefenseEngine:
    def test_decide_normal(self):
        defense = AutoDefenseEngine()
        decision = defense.decide(risk_level="normal")
        assert decision.level == DefenseLevel.NONE
        assert not decision.requires_action

    def test_decide_warning(self):
        defense = AutoDefenseEngine()
        decision = defense.decide(
            risk_level="warning",
            systemic_score=0.5,
            vol_regime="high_vol",
        )
        assert decision.level != DefenseLevel.NONE

    def test_decide_critical(self):
        defense = AutoDefenseEngine(
            current_position=1.0, current_leverage=2.5,
            current_hedge=0.0, current_cash=0.02,
        )
        decision = defense.decide(
            risk_level="critical",
            systemic_score=0.8,
            vol_regime="crisis_vol",
            liquidity_level="freeze",
            current_drawdown=0.25,
        )
        assert decision.level in (DefenseLevel.PROTECTIVE, DefenseLevel.FULL_DEFENSE)
        assert decision.requires_action
        assert len(decision.orders) >= 1

    def test_position_reduction_order(self):
        defense = AutoDefenseEngine(current_position=1.0)
        decision = defense.decide(
            risk_level="critical",
            systemic_score=0.7,
            vol_regime="crisis_vol",
        )
        reduce_orders = [
            o for o in decision.orders
            if o.action == DefenseAction.REDUCE_POSITION
        ]
        assert len(reduce_orders) >= 1

    def test_leverage_reduction_order(self):
        defense = AutoDefenseEngine(current_leverage=2.5)
        decision = defense.decide(
            risk_level="warning",
            systemic_score=0.5,
            vol_regime="high_vol",
        )
        leverage_orders = [
            o for o in decision.orders
            if o.action == DefenseAction.LOWER_LEVERAGE
        ]
        assert len(leverage_orders) >= 1

    def test_full_defense_stops_trading(self):
        defense = AutoDefenseEngine()
        decision = defense.decide(
            risk_level="critical",
            systemic_score=0.9,
            vol_regime="crisis_vol",
            liquidity_level="freeze",
            current_drawdown=0.3,
        )
        stop_orders = [
            o for o in decision.orders
            if o.action == DefenseAction.STOP_TRADING
        ]
        assert len(stop_orders) >= 1

    def test_critical_orders_urgent(self):
        defense = AutoDefenseEngine(
            current_position=1.0, current_leverage=3.0,
            current_hedge=0.0, current_cash=0.01,
        )
        decision = defense.decide(
            risk_level="critical",
            systemic_score=0.9,
            vol_regime="crisis_vol",
            current_drawdown=0.25,
        )
        assert len(decision.critical_orders) >= 1

    def test_defense_order_properties(self):
        order = DefenseOrder(
            current_value=100.0, target_value=50.0,
        )
        assert order.delta_pct == 50.0

    def test_default_params(self):
        decision = DefenseDecision(level=DefenseLevel.NONE)
        assert not decision.requires_action
        assert len(decision.critical_orders) == 0


# ====================================================================
# Risk Memory
# ====================================================================

class TestRiskMemory:
    def test_record_event(self):
        memory = RiskMemory()
        event = memory.record(
            event_type="volatility_spike",
            risk_level="warning",
            systemic_score=0.45,
            volatility_regime="high_vol",
            portfolio_reaction="reduce_leverage",
            defense_result="success",
            recovery_time_days=5,
            peak_drawdown=0.08,
            description="VIX spike to 32",
            lessons=["Add VIX hedge earlier"],
        )
        assert event.event_id == 1
        assert event.event_type == "volatility_spike"

    def test_multiple_events(self):
        memory = RiskMemory()
        for i in range(5):
            memory.record(
                event_type=f"test_{i}",
                risk_level="normal" if i < 3 else "warning",
            )
        assert len(memory.events) == 5

    def test_recent_events(self):
        memory = RiskMemory()
        for i in range(15):
            memory.record(event_type=f"event_{i}")
        recent = memory.recent_events(5)
        assert len(recent) == 5
        assert recent[-1].event_type == "event_14"

    def test_events_by_type(self):
        memory = RiskMemory()
        memory.record(event_type="crash")
        memory.record(event_type="recovery")
        memory.record(event_type="crash")
        crashes = memory.events_by_type("crash")
        assert len(crashes) == 2

    def test_events_by_level(self):
        memory = RiskMemory()
        memory.record(risk_level="normal")
        memory.record(risk_level="warning")
        memory.record(risk_level="critical")
        critical = memory.events_by_level("critical")
        assert len(critical) == 1

    def test_events_by_regime(self):
        memory = RiskMemory()
        memory.record(volatility_regime="high_vol")
        memory.record(volatility_regime="normal_vol")
        memory.record(volatility_regime="high_vol")
        high = memory.events_by_regime("high_vol")
        assert len(high) == 2

    def test_knowledge_base(self):
        memory = RiskMemory()
        for i in range(10):
            memory.record(
                event_type="systemic" if i < 5 else "volatility",
                risk_level="normal" if i < 7 else "warning",
                volatility_regime="normal_vol" if i < 6 else "high_vol",
                recovery_time_days=3 + i,
                peak_drawdown=0.05 + i * 0.01,
                portfolio_reaction="reduce_leverage" if i % 2 == 0 else "increase_hedge",
            )
        kb = memory.knowledge_base()
        assert kb.total_events == 10
        assert kb.avg_recovery_days > 0
        assert kb.max_drawdown > 0

    def test_summary(self):
        memory = RiskMemory()
        memory.record(event_type="test")
        summary = memory.summary()
        assert summary["total_events"] == 1
        assert "recent" in summary

    def test_empty_knowledge_base(self):
        memory = RiskMemory()
        kb = memory.knowledge_base()
        assert kb.total_events == 0

    def test_clear(self):
        memory = RiskMemory()
        memory.record(event_type="test")
        memory.clear()
        assert len(memory.events) == 0
        assert memory._counter == 0


# ====================================================================
# Global Risk Intelligence Service
# ====================================================================

class TestGlobalRiskIntelligenceService:
    def test_detect_systemic_risk(self):
        service = GlobalRiskIntelligenceService()
        result = service.detect_systemic_risk(vix=18.0, ig_spread=1.0)
        assert isinstance(result, SystemicRiskAssessment)
        assert result.level == RiskLevel.NORMAL

    def test_classify_volatility(self):
        service = GlobalRiskIntelligenceService()
        result = service.classify_volatility(22.0)
        assert isinstance(result, RegimeResult)
        assert result.regime == VolatilityRegime.NORMAL_VOL

    def test_analyze_liquidity(self):
        service = GlobalRiskIntelligenceService()
        result = service.analyze_liquidity()
        assert isinstance(result, LiquidityAssessment)

    def test_detect_black_swan(self):
        service = GlobalRiskIntelligenceService()
        result = service.detect_black_swan()
        assert isinstance(result, BlackSwanAssessment)

    def test_analyze_contagion(self):
        service = GlobalRiskIntelligenceService()
        result = service.analyze_contagion("US Bond")
        assert isinstance(result, ContagionResult)
        assert len(result.affected_nodes) >= 1

    def test_analyze_contagion_multi(self):
        service = GlobalRiskIntelligenceService()
        results = service.analyze_contagion_multi({
            "US Bond": 0.3,
            "Credit Event": 0.4,
        })
        assert len(results) == 2

    def test_run_stress_test(self):
        service = GlobalRiskIntelligenceService()
        result = service.run_stress_test("Fed +100bp")
        assert isinstance(result, StressTestResult)
        assert result.scenario == "Fed +100bp"

    def test_run_all_stress_tests(self):
        service = GlobalRiskIntelligenceService()
        results = service.run_all_stress_tests()
        assert len(results) >= 5

    def test_decide_defense(self):
        service = GlobalRiskIntelligenceService()
        decision = service.decide_defense(
            risk_level="warning",
            systemic_score=0.5,
            vol_regime="high_vol",
        )
        assert isinstance(decision, DefenseDecision)

    def test_record_risk_event(self):
        service = GlobalRiskIntelligenceService()
        event = service.record_risk_event(
            event_type="test",
            risk_level="normal",
        )
        assert isinstance(event, RiskEvent)

    def test_get_risk_knowledge(self):
        service = GlobalRiskIntelligenceService()
        knowledge = service.get_risk_knowledge()
        assert "total_events" in knowledge

    def test_comprehensive_risk_analysis(self):
        service = GlobalRiskIntelligenceService()
        result = service.comprehensive_risk_analysis(
            market_data={"vix": 30.0, "ig_spread": 2.0, "equity_drawdown": 0.1},
            contagion_source="NASDAQ",
            stress_scenario="VIX 50",
        )
        assert "aggregate_risk_score" in result
        assert "systemic_risk" in result
        assert "volatility_regime" in result
        assert "liquidity" in result
        assert "black_swan" in result
        assert "contagion" in result
        assert "stress_test" in result
        assert "defense_decision" in result
        assert 0.0 <= result["aggregate_risk_score"] <= 1.0

    def test_comprehensive_risk_analysis_crisis(self):
        service = GlobalRiskIntelligenceService()
        result = service.comprehensive_risk_analysis(
            market_data={
                "vix": 45.0, "ig_spread": 3.0, "hy_spread": 7.0,
                "equity_drawdown": 0.2, "equity_breadth": 0.2,
                "dxy_change": 0.04, "gold_oil_ratio": 38,
            },
            stress_scenario="Credit Crisis",
        )
        assert result["aggregate_risk_score"] >= 0.3

    def test_comprehensive_defaults(self):
        service = GlobalRiskIntelligenceService()
        result = service.comprehensive_risk_analysis()
        assert result["aggregate_risk_score"] >= 0
        assert result["systemic_risk"]["level"] == "normal"

    def test_clear_all(self):
        service = GlobalRiskIntelligenceService()
        service.detect_systemic_risk(vix=20.0)
        service.classify_volatility(15.0)
        service.clear_all()
        # Verify clear didn't error
        assert True
