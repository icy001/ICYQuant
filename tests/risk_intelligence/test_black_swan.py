from services.risk_intelligence import (
    BlackSwanDetector,
    BlackSwanLevel,
)


class TestBlackSwanDetection:
    def test_no_black_swan(self):
        detector = BlackSwanDetector()
        result = detector.detect(index_decline=0.01, vix_change=0.1, volume_surge=1.0, bid_ask_spread=0.0005)
        assert result.level == BlackSwanLevel.NONE.value
        assert result.detected is False

    def test_warning_level(self):
        detector = BlackSwanDetector()
        result = detector.detect(index_decline=-0.06, vix_change=0.3, volume_surge=2.0, bid_ask_spread=0.003)
        assert result.level == BlackSwanLevel.WARNING.value
        assert result.detected is True

    def test_critical_level(self):
        detector = BlackSwanDetector()
        result = detector.detect(index_decline=-0.12, vix_change=0.8, volume_surge=4.0, bid_ask_spread=0.008)
        assert result.level == BlackSwanLevel.CRITICAL.value
        assert result.detected is True

    def test_extreme_level(self):
        detector = BlackSwanDetector()
        result = detector.detect(index_decline=-0.20, vix_change=2.0, volume_surge=10.0, bid_ask_spread=0.025)
        assert result.level == BlackSwanLevel.EXTREME.value
        assert result.detected is True

    def test_liquidity_drought_detection(self):
        detector = BlackSwanDetector()
        result = detector.detect(index_decline=-0.02, vix_change=0.2, volume_surge=1.5, bid_ask_spread=0.008)
        assert result.liquidity_drought is True

    def test_abnormal_volume_detection(self):
        detector = BlackSwanDetector()
        result = detector.detect(index_decline=-0.01, vix_change=0.1, volume_surge=4.0, bid_ask_spread=0.001)
        assert result.abnormal_volume is True
