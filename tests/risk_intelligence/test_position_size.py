from services.risk_intelligence import (
    DynamicPositionSizer,
    RiskPredictor,
    MarketRegimeDetector,
    BlackSwanDetector,
    BlackSwanLevel,
    MarketRegimeType,
)


class TestDynamicPositionSizing:
    def test_normal_conditions(self):
        sizer = DynamicPositionSizer()
        predictor = RiskPredictor()
        regime_detector = MarketRegimeDetector()
        bs_detector = BlackSwanDetector()

        prediction = predictor.predict(volatility=0.15, liquidity=0.85)
        regime = regime_detector.detect(trend=0.015, volatility=0.12)
        bs_event = bs_detector.detect()

        result = sizer.size(
            signal_confidence=0.85,
            risk_prediction=prediction,
            market_regime=regime,
            black_swan=bs_event,
            liquidity_score=0.85,
            max_portfolio_pct=0.10,
        )
        assert result.adjusted_pct > 0
        assert result.adjusted_pct <= result.theoretical_pct

    def test_black_swan_extreme_reduces_to_zero(self):
        sizer = DynamicPositionSizer()
        predictor = RiskPredictor()
        regime_detector = MarketRegimeDetector()
        bs_detector = BlackSwanDetector()

        prediction = predictor.predict(volatility=0.15)
        regime = regime_detector.detect(trend=0.01)
        bs_event = bs_detector.detect(index_decline=-0.20, vix_change=2.0, volume_surge=10.0, bid_ask_spread=0.03)

        result = sizer.size(
            signal_confidence=0.9,
            risk_prediction=prediction,
            market_regime=regime,
            black_swan=bs_event,
            max_portfolio_pct=0.10,
        )
        assert result.adjusted_pct == 0.0

    def test_risk_off_market_reduces_position(self):
        sizer = DynamicPositionSizer()
        predictor = RiskPredictor()
        regime_detector = MarketRegimeDetector()
        bs_detector = BlackSwanDetector()

        prediction = predictor.predict(volatility=0.25, liquidity=0.5)
        regime = regime_detector.detect(trend=-0.03, volatility=0.4, spread=0.005)
        bs_event = bs_detector.detect(index_decline=-0.01)

        result = sizer.size(
            signal_confidence=0.9,
            risk_prediction=prediction,
            market_regime=regime,
            black_swan=bs_event,
            max_portfolio_pct=0.10,
        )
        assert result.adjusted_pct < 0.05

    def test_signal_confidence_affects_size(self):
        sizer = DynamicPositionSizer()
        predictor = RiskPredictor()
        regime_detector = MarketRegimeDetector()
        bs_detector = BlackSwanDetector()

        prediction = predictor.predict(volatility=0.1)
        regime = regime_detector.detect(trend=0.02)
        bs_event = bs_detector.detect()

        high_conf = sizer.size(
            signal_confidence=0.95,
            risk_prediction=prediction,
            market_regime=regime,
            black_swan=bs_event,
            max_portfolio_pct=0.10,
        )

        low_conf = sizer.size(
            signal_confidence=0.5,
            risk_prediction=prediction,
            market_regime=regime,
            black_swan=bs_event,
            max_portfolio_pct=0.10,
        )

        assert high_conf.adjusted_pct > low_conf.adjusted_pct

    def test_position_can_never_be_negative(self):
        sizer = DynamicPositionSizer()
        result = sizer.size(signal_confidence=0.1, max_portfolio_pct=0.10)
        assert result.adjusted_pct >= 0.0
