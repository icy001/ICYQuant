from services.risk_intelligence import (
    AdaptiveLimitManager,
    RiskLimitConfig,
    RiskPredictor,
    MarketRegimeDetector,
    BlackSwanDetector,
    BlackSwanLevel,
    MarketRegimeType,
    AdaptiveController,
    RiskIntelligenceService,
    EmergencyLevel,
    StressTestingEngine,
    ScenarioEngine,
    ExposureEngine,
    PortfolioRiskEngine,
)


class TestAdaptiveLimits:
    def test_market_regime_tightens_limits(self):
        manager = AdaptiveLimitManager()
        detector = MarketRegimeDetector()

        bull_regime = detector.detect(trend=0.03, volatility=0.1)
        bull_result = manager.apply_market_regime(bull_regime)

        bear_regime = detector.detect(trend=-0.03, volatility=0.25, spread=0.003)
        bear_result = manager.apply_market_regime(bear_regime)

        assert bull_result.adjusted_config.max_drawdown_pct >= bear_result.adjusted_config.max_drawdown_pct

    def test_black_swan_extreme_halts_trading(self):
        manager = AdaptiveLimitManager()
        detector = BlackSwanDetector()

        bs_event = detector.detect(index_decline=-0.20, vix_change=2.0, volume_surge=10.0, bid_ask_spread=0.03)
        result = manager.apply_black_swan(bs_event)

        assert result.adjusted_config.max_position_pct == 0.0
        assert result.adjusted_config.max_leverage == 1.0
        assert result.tightened is True

    def test_high_risk_tightens_limits(self):
        manager = AdaptiveLimitManager()
        predictor = RiskPredictor()

        high_risk = predictor.predict(volatility=0.5, liquidity=0.3)
        result = manager.apply_risk_prediction(high_risk)

        assert result.adjusted_config.max_drawdown_pct < manager.base_config.max_drawdown_pct
        assert result.tightened is True

    def test_low_risk_maintains_limits(self):
        manager = AdaptiveLimitManager()
        predictor = RiskPredictor()

        low_risk = predictor.predict(volatility=0.1, liquidity=0.95, credit_spread=0.02, var_95=0.01)
        result = manager.apply_risk_prediction(low_risk)

        assert result.tightened is False


class TestStressTesting:
    def test_market_crash_scenario(self):
        engine = StressTestingEngine()
        result = engine.run_stress_test(scenario_name="market_crash", capital_threshold=0.05)
        assert result.scenario_name == "market_crash"
        assert result.estimated_loss_pct < 0
        assert result.passed is False
        assert len(result.warnings) > 0

    def test_recession_scenario(self):
        engine = StressTestingEngine()
        result = engine.run_stress_test(scenario_name="recession", capital_threshold=0.10)
        assert result.scenario_name == "recession"

    def test_unknown_scenario(self):
        engine = StressTestingEngine()
        result = engine.run_stress_test(scenario_name="nonexistent")
        assert result.warnings
        assert "not found" in result.warnings[0]

    def test_list_scenarios(self):
        engine = StressTestingEngine()
        scenarios = engine.list_scenarios()
        assert "market_crash" in scenarios
        assert "recession" in scenarios


class TestScenarioEngine:
    def test_covid_scenario(self):
        engine = ScenarioEngine()
        result = engine.run_scenario("COVID2020", {"technology": 0.3, "financial": 0.2, "energy": 0.1})
        assert result.scenario_name == "COVID2020"
        assert result.portfolio_pnl_pct < 0
        assert result.risk_level in ("HIGH", "CRITICAL")

    def test_ai_rally_scenario(self):
        engine = ScenarioEngine()
        result = engine.run_scenario("AIRally2024", {"technology": 0.5, "semiconductors": 0.3})
        assert result.portfolio_pnl_pct > 0

    def test_list_scenarios(self):
        engine = ScenarioEngine()
        scenarios = engine.list_scenarios()
        assert len(scenarios) >= 5


class TestExposureEngine:
    def test_generate_report(self):
        engine = ExposureEngine(total_risk_budget=1.0)
        engine.set_limits(sector_limits={"technology": 0.40, "financial": 0.30})
        report = engine.generate_report(
            sector_exposure={"technology": 0.35, "financial": 0.15},
            strategy_exposure={"strategy_a": 0.25},
        )
        assert report.total_exposure == 0.50
        assert report.used_risk_budget_pct == 0.50
        assert report.remaining_budget_pct == 0.50

    def test_violation_detection(self):
        engine = ExposureEngine(total_risk_budget=1.0)
        engine.set_limits(sector_limits={"technology": 0.40})
        report = engine.generate_report(sector_exposure={"technology": 0.50})
        assert len(report.violations) > 0


class TestPortfolioRisk:
    def test_var_calculation(self):
        engine = PortfolioRiskEngine()
        returns = [0.01, -0.02, 0.03, -0.01, 0.02, -0.05, 0.04, -0.03, 0.01, -0.02]
        var = engine.calculate_var(returns)
        assert var > 0
        assert var <= 0.1

    def test_portfolio_evaluation(self):
        engine = PortfolioRiskEngine()
        returns = [0.01, -0.02, 0.03, -0.01, 0.02]
        result = engine.evaluate_portfolio(
            returns=returns,
            sector_exposures={"technology": 0.35, "cash": 0.65},
            factor_exposures={"market": 1.0, "technology": 0.8},
        )
        assert result.total_exposure == 1.0
        assert len(result.sector_exposures) == 2

    def test_sector_exposure_over_limit(self):
        engine = PortfolioRiskEngine()
        exposure = engine.assess_sector_exposure("technology", 0.50)
        assert exposure.over_limit is True


class TestAdaptiveController:
    def test_normal_evaluation(self):
        controller = AdaptiveController()
        result = controller.evaluate(
            volatility=0.1,
            liquidity=0.9,
            trend=0.02,
        )
        assert result.emergency_level == EmergencyLevel.NORMAL.value
        assert result.can_trade is True
        assert result.position_size.adjusted_pct > 0

    def test_emergency_stop(self):
        controller = AdaptiveController()
        result = controller.emergency_stop()
        assert result.emergency_level == EmergencyLevel.HALT.value
        assert result.can_trade is False
        assert result.actions.cancel_orders is True
        assert result.actions.freeze_agents is True

    def test_resume_trading(self):
        controller = AdaptiveController()
        controller.emergency_stop()
        result = controller.resume_trading()
        assert result.emergency_level == EmergencyLevel.NORMAL.value
        assert result.can_trade is True

    def test_black_swan_triggers_halt(self):
        controller = AdaptiveController()
        result = controller.evaluate(
            volatility=0.45,
            index_decline=-0.20,
            vix_change=2.0,
            volume_surge=10.0,
            bid_ask_spread=0.03,
        )
        assert result.emergency_level == EmergencyLevel.HALT.value
        assert result.can_trade is False

    def test_high_risk_restricts(self):
        controller = AdaptiveController()
        result = controller.evaluate(volatility=0.5, liquidity=0.3)
        assert result.emergency_level == EmergencyLevel.RESTRICT.value


class TestFullService:
    def test_risk_score_endpoint(self):
        service = RiskIntelligenceService()
        result = service.get_risk_score(volatility=0.3, liquidity=0.6)
        assert result.risk_score > 0
        assert result.risk_level in ("LOW", "MEDIUM", "HIGH")

    def test_full_assessment(self):
        service = RiskIntelligenceService()
        result = service.full_risk_assessment(volatility=0.15, trend=0.02)
        assert result.emergency_level
        assert result.can_trade is True

    def test_stress_test_via_service(self):
        service = RiskIntelligenceService()
        result = service.run_stress_test(scenario_name="market_crash")
        assert result.estimated_loss_pct < 0

    def test_exposure_report_via_service(self):
        service = RiskIntelligenceService()
        result = service.get_exposure_report(sector_exposure={"technology": 0.3})
        assert result.total_exposure == 0.3

    def test_position_size_via_service(self):
        service = RiskIntelligenceService()
        result = service.calculate_position_size(signal_confidence=0.8, volatility=0.15)
        assert result.adjusted_pct > 0

    def test_emergency_stop_via_service(self):
        service = RiskIntelligenceService()
        result = service.emergency_stop()
        assert result.emergency_level == EmergencyLevel.HALT.value

    def test_scenario_via_service(self):
        service = RiskIntelligenceService()
        result = service.run_scenario("COVID2020", {"technology": 0.3})
        assert result.scenario_name == "COVID2020"
