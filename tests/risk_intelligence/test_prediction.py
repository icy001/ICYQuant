from services.risk_intelligence import (
    RiskPredictor,
    RiskLevel,
    MarketRegimeDetector,
    MarketRegimeType,
    BlackSwanDetector,
    BlackSwanLevel,
    DynamicPositionSizer,
    StressTestingEngine,
    ScenarioEngine,
    PortfolioRiskEngine,
    ExposureEngine,
    AdaptiveLimitManager,
    AdaptiveController,
    RiskIntelligenceService,
    EmergencyLevel,
)


class TestRiskPredictor:
    def test_low_risk_prediction(self):
        predictor = RiskPredictor()
        result = predictor.predict(volatility=0.1, liquidity=0.95, credit_spread=0.02, var_95=0.01)
        assert result.risk_level == RiskLevel.LOW.value
        assert result.risk_score <= 30

    def test_high_risk_prediction(self):
        predictor = RiskPredictor()
        result = predictor.predict(volatility=0.5, liquidity=0.4, credit_spread=0.15, var_95=0.08)
        assert result.risk_level == RiskLevel.HIGH.value
        assert result.risk_score > 70
        assert result.recommendation == "Reduce Exposure"

    def test_medium_risk_prediction(self):
        predictor = RiskPredictor()
        result = predictor.predict(volatility=0.25, liquidity=0.7, credit_spread=0.05, var_95=0.03)
        assert result.risk_level == RiskLevel.MEDIUM.value

    def test_risk_score_range(self):
        predictor = RiskPredictor()
        for vol in [0.05, 0.2, 0.5]:
            result = predictor.predict(volatility=vol)
            assert 0 <= result.risk_score <= 100


class TestMarketRegimeDetection:
    def test_bull_market(self):
        detector = MarketRegimeDetector()
        result = detector.detect(trend=0.03, volatility=0.1)
        assert result.regime_type == MarketRegimeType.BULL.value
        assert result.max_position_pct >= 0.08

    def test_risk_off(self):
        detector = MarketRegimeDetector()
        result = detector.detect(trend=-0.02, volatility=0.4, spread=0.005)
        assert result.regime_type == MarketRegimeType.RISK_OFF.value
        assert result.max_position_pct <= 0.03

    def test_high_volatility(self):
        detector = MarketRegimeDetector()
        result = detector.detect(trend=0.01, volatility=0.3)
        assert result.regime_type == MarketRegimeType.HIGH_VOLATILITY.value

    def test_sideway_market(self):
        detector = MarketRegimeDetector()
        result = detector.detect(trend=0.005, volatility=0.12)
        assert result.regime_type == MarketRegimeType.SIDEWAY.value
