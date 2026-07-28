"""Tests for the AI Market Regime Intelligence Engine."""

import pytest

from services.market_regime import (
    MacroAnalyzer,
    MarketRegime,
    MarketRegimeService,
    RegimeClassifier,
    RegimeMemory,
    RegimeRecord,
    RegimeState,
    RegimeTransition,
    StrategyMatcher,
    TrendDetector,
    VolatilityDetector,
)


# =============================================================================
# MarketRegime tests
# =============================================================================

class TestMarketRegime:
    """Test MarketRegime model."""

    def test_create_regime(self):
        regime = MarketRegime(state="BULL_TREND", confidence=0.85)
        assert regime.state == "BULL_TREND"
        assert regime.confidence == 0.85

    def test_default_values(self):
        regime = MarketRegime(state="SIDEWAYS")
        assert regime.confidence == 0.0
        assert regime.trend_strength == 0.0
        assert regime.suggested_exposure == 1.0

    def test_is_bull(self):
        assert MarketRegime(state="BULL_TREND").is_bull is True
        assert MarketRegime(state="BULL_LOW_VOL").is_bull is True
        assert MarketRegime(state="BEAR_TREND").is_bull is False

    def test_is_bear(self):
        assert MarketRegime(state="BEAR_TREND").is_bear is True
        assert MarketRegime(state="BEAR_HIGH_VOL").is_bear is True
        assert MarketRegime(state="BULL_TREND").is_bear is False

    def test_is_sideways(self):
        assert MarketRegime(state="SIDEWAYS").is_sideways is True
        assert MarketRegime(state="SIDEWAYS_LOW_VOL").is_sideways is True
        assert MarketRegime(state="BULL_TREND").is_sideways is False

    def test_is_high_volatility(self):
        assert MarketRegime(state="BULL_HIGH_VOL").is_high_volatility is True
        assert MarketRegime(state="CRISIS").is_high_volatility is True
        assert MarketRegime(state="BULL_LOW_VOL").is_high_volatility is False

    def test_is_low_volatility(self):
        assert MarketRegime(state="BULL_LOW_VOL").is_low_volatility is True
        assert MarketRegime(state="BULL_HIGH_VOL").is_low_volatility is False

    def test_is_crisis(self):
        assert MarketRegime(state="CRISIS").is_crisis is True
        assert MarketRegime(state="BULL_TREND").is_crisis is False

    def test_is_risk_on(self):
        regime = MarketRegime(state="BULL_TREND", macro_signal="RISK_ON")
        assert regime.is_risk_on is True
        assert regime.is_risk_off is False

    def test_is_risk_off(self):
        regime = MarketRegime(state="BEAR_TREND", macro_signal="RISK_OFF")
        assert regime.is_risk_off is True
        assert regime.is_risk_on is False

        regime2 = MarketRegime(state="BEAR_TREND", macro_signal="FLIGHT_TO_QUALITY")
        assert regime2.is_risk_off is True

    def test_to_dict(self):
        regime = MarketRegime(
            state="BULL_LOW_VOL",
            confidence=0.9,
            trend_signal="STRONG_UPTREND",
            trend_strength=0.8,
            volatility_signal="LOW",
            volatility_level=0.15,
            macro_signal="RISK_ON",
            recommended_strategies=["momentum", "growth"],
            suggested_exposure=0.9,
        )
        d = regime.to_dict()
        assert d["state"] == "BULL_LOW_VOL"
        assert d["confidence"] == 0.9
        assert d["trend_signal"] == "STRONG_UPTREND"
        assert d["recommended_strategies"] == ["momentum", "growth"]

    def test_summary(self):
        regime = MarketRegime(
            state="BULL_LOW_VOL",
            confidence=0.9,
            trend_signal="UPTREND",
            trend_strength=0.7,
            volatility_signal="LOW",
            macro_signal="RISK_ON",
        )
        summary = regime.summary()
        assert "BULL_LOW_VOL" in summary
        assert "90.0%" in summary or "0.90" in summary or "0.9" in summary


class TestRegimeState:
    """Test RegimeState enumeration."""

    def test_all_states(self):
        states = RegimeState.all_states()
        assert "BULL_TREND" in states
        assert "BEAR_TREND" in states
        assert "SIDEWAYS" in states
        assert "CRISIS" in states
        assert "RISK_ON" in states
        assert "RISK_OFF" in states

    def test_trend_states(self):
        states = RegimeState.trend_states()
        assert "BULL_TREND" in states
        assert "BEAR_TREND" in states
        assert "SIDEWAYS" in states

    def test_volatility_states(self):
        states = RegimeState.volatility_states()
        assert "LOW_VOLATILITY" in states
        assert "HIGH_VOLATILITY" in states
        assert "CRISIS" in states

    def test_macro_states(self):
        states = RegimeState.macro_states()
        assert "RISK_ON" in states
        assert "RISK_OFF" in states
        assert "FLIGHT_TO_QUALITY" in states


class TestRegimeTransition:
    """Test RegimeTransition model."""

    def test_create_transition(self):
        t = RegimeTransition(
            from_state="BULL_TREND",
            to_state="SIDEWAYS",
            confidence=0.7,
            trigger_factors=["VIX spike", "MA crossover"],
        )
        assert t.from_state == "BULL_TREND"
        assert t.to_state == "SIDEWAYS"
        assert len(t.trigger_factors) == 2

    def test_to_dict(self):
        t = RegimeTransition(
            from_state="BULL_TREND",
            to_state="BEAR_TREND",
            confidence=0.85,
        )
        d = t.to_dict()
        assert d["from_state"] == "BULL_TREND"
        assert d["to_state"] == "BEAR_TREND"


# =============================================================================
# TrendDetector tests
# =============================================================================

class TestTrendDetector:
    """Test trend detector."""

    def test_detect_legacy_interface(self):
        detector = TrendDetector()
        result = detector.detect({"price": 105, "ma_fast": 100, "ma_slow": 95})
        assert result["trend"] in TrendDetector.TREND_DIRECTIONS

    def test_strong_uptrend(self):
        detector = TrendDetector()
        data = {
            "price": 110,
            "ma_fast": 100,
            "ma_slow": 90,
            "ma_long": 80,
            "momentum": 10,
            "adx": 30,
            "breadth": 2.0,
            "consecutive_up": 6,
        }
        trend = detector.classify_trend(data)
        assert trend in ("STRONG_UPTREND", "UPTREND")

    def test_strong_downtrend(self):
        detector = TrendDetector()
        data = {
            "price": 80,
            "ma_fast": 90,
            "ma_slow": 100,
            "ma_long": 110,
            "momentum": -10,
            "adx": 30,
            "breadth": 0.5,
            "consecutive_down": 6,
        }
        trend = detector.classify_trend(data)
        assert trend in ("STRONG_DOWNTREND", "DOWNTREND")

    def test_neutral_trend(self):
        detector = TrendDetector()
        # No strong directional signals → neutral
        data = {
            "price": 100,
            "momentum": 2,  # small momentum, within ±5
            "adx": 10,      # below threshold, no trend
            "breadth": 1.0,
        }
        trend = detector.classify_trend(data)
        assert trend == "NEUTRAL"

    def test_trend_strength_range(self):
        detector = TrendDetector()
        data = {"price": 110, "ma_fast": 100, "ma_slow": 95}
        strength = detector.trend_strength(data)
        assert -1.0 <= strength <= 1.0

    def test_trend_strength_bull(self):
        detector = TrendDetector()
        data = {
            "price": 120, "ma_fast": 100, "ma_slow": 90,
            "ma_long": 80, "momentum": 8, "adx": 30,
            "consecutive_up": 5,
        }
        strength = detector.trend_strength(data)
        assert strength > 0

    def test_trend_strength_bear(self):
        detector = TrendDetector()
        data = {
            "price": 80, "ma_fast": 100, "ma_slow": 110,
            "ma_long": 120, "momentum": -8, "adx": 30,
            "consecutive_down": 5,
        }
        strength = detector.trend_strength(data)
        assert strength < 0

    def test_detect_with_details(self):
        detector = TrendDetector()
        data = {"price": 105, "ma_fast": 100, "ma_slow": 95, "adx": 30}
        details = detector.detect_with_details(data)
        assert "trend" in details
        assert "strength" in details
        assert "confidence" in details
        assert "signals" in details
        assert 0.0 <= details["confidence"] <= 1.0

    def test_to_regime_bull(self):
        detector = TrendDetector()
        assert detector.to_regime("STRONG_UPTREND") == "BULL_TREND"
        assert detector.to_regime("UPTREND") == "BULL_TREND"
        assert detector.to_regime("WEAK_UPTREND") == "BULL_TREND"

    def test_to_regime_bear(self):
        detector = TrendDetector()
        assert detector.to_regime("STRONG_DOWNTREND") == "BEAR_TREND"
        assert detector.to_regime("DOWNTREND") == "BEAR_TREND"
        assert detector.to_regime("WEAK_DOWNTREND") == "BEAR_TREND"

    def test_to_regime_neutral(self):
        detector = TrendDetector()
        assert detector.to_regime("NEUTRAL") == "SIDEWAYS"

    def test_empty_data(self):
        detector = TrendDetector()
        trend = detector.classify_trend({})
        assert trend == "NEUTRAL"
        strength = detector.trend_strength({})
        assert strength == 0.0


# =============================================================================
# VolatilityDetector tests
# =============================================================================

class TestVolatilityDetector:
    """Test volatility detector."""

    def test_detect_legacy_high(self):
        detector = VolatilityDetector()
        assert detector.detect(35) == "HIGH"

    def test_detect_legacy_low(self):
        detector = VolatilityDetector()
        assert detector.detect(10) == "LOW"

    def test_detect_legacy_normal(self):
        detector = VolatilityDetector()
        assert detector.detect(20) == "NORMAL"

    def test_detect_legacy_elevated(self):
        detector = VolatilityDetector()
        result = detector.detect(28)
        assert result in ("ELEVATED", "NORMAL")  # depends on threshold

    def test_classify_vix_extreme(self):
        detector = VolatilityDetector()
        regime = detector.classify_volatility(vix=35)
        assert regime == "EXTREME"

    def test_classify_vix_high(self):
        detector = VolatilityDetector()
        regime = detector.classify_volatility(vix=28)
        assert regime in ("HIGH", "ELEVATED")

    def test_classify_vix_low(self):
        detector = VolatilityDetector()
        regime = detector.classify_volatility(vix=11)
        assert regime == "EXTREMELY_LOW"

    def test_classify_vix_normal(self):
        detector = VolatilityDetector()
        regime = detector.classify_volatility(vix=18)
        assert regime == "NORMAL"

    def test_classify_historical_vol(self):
        detector = VolatilityDetector()
        regime = detector.classify_volatility(historical_vol=40)
        assert regime in ("EXTREME", "HIGH")

    def test_classify_vol_percentile(self):
        detector = VolatilityDetector()
        regime = detector.classify_volatility(vol_percentile=95)
        assert regime == "EXTREME"

        regime = detector.classify_volatility(vol_percentile=5)
        assert regime == "EXTREMELY_LOW"

    def test_classify_default_normal(self):
        detector = VolatilityDetector()
        regime = detector.classify_volatility()
        assert regime == "NORMAL"

    def test_volatility_level(self):
        detector = VolatilityDetector()
        level = detector.volatility_level(vix=25)
        assert 0.0 <= level <= 1.0
        assert level > 0.4  # VIX 25 should be above middle

    def test_volatility_level_low(self):
        detector = VolatilityDetector()
        level = detector.volatility_level(vix=12)
        assert level < 0.2

    def test_detect_with_details(self):
        detector = VolatilityDetector()
        details = detector.detect_with_details(vix=18, vol_change=10)
        assert details["regime"] in VolatilityDetector.VOL_REGIMES
        assert "level" in details
        assert "vol_trend" in details

    def test_to_macro_signal(self):
        detector = VolatilityDetector()
        assert detector.to_macro_signal("EXTREME") == "RISK_OFF"
        assert detector.to_macro_signal("HIGH") == "RISK_OFF"
        assert detector.to_macro_signal("ELEVATED") == "FLIGHT_TO_QUALITY"
        assert detector.to_macro_signal("LOW") == "RISK_ON"

    def test_suggested_exposure(self):
        detector = VolatilityDetector()
        assert detector.suggested_exposure("LOW") == 1.0
        assert detector.suggested_exposure("EXTREME") < 0.5


# =============================================================================
# MacroAnalyzer tests
# =============================================================================

class TestMacroAnalyzer:
    """Test macro analyzer."""

    def test_analyze_legacy_interface(self):
        analyzer = MacroAnalyzer()
        result = analyzer.analyze({"gdp_growth": 3.0, "inflation": 2.0})
        assert "environment" in result

    def test_goldilocks(self):
        analyzer = MacroAnalyzer()
        env = analyzer.classify_environment({
            "gdp_growth": 3.0,
            "inflation": 2.0,
            "rate_change": 0.0,
        })
        assert env == "GOLDILOCKS"

    def test_recession(self):
        analyzer = MacroAnalyzer()
        env = analyzer.classify_environment({
            "gdp_growth": -1.0,
            "inflation": 2.0,
        })
        assert env == "RECESSION"

    def test_stagflation(self):
        analyzer = MacroAnalyzer()
        env = analyzer.classify_environment({
            "gdp_growth": 0.5,
            "inflation": 5.0,
        })
        assert env == "STAGFLATION"

    def test_tightening(self):
        analyzer = MacroAnalyzer()
        env = analyzer.classify_environment({
            "gdp_growth": 3.0,
            "inflation": 3.0,
            "rate_change": 0.5,
        })
        assert env == "TIGHTENING"

    def test_easing(self):
        analyzer = MacroAnalyzer()
        env = analyzer.classify_environment({
            "gdp_growth": 2.0,
            "inflation": 2.0,
            "rate_change": -0.5,
        })
        assert env == "EASING"

    def test_recovery(self):
        analyzer = MacroAnalyzer()
        env = analyzer.classify_environment({
            "gdp_growth": 1.0,
            "inflation": 1.5,
            "rate_change": 0.0,
        })
        assert env == "RECOVERY"

    def test_growth_inflation(self):
        analyzer = MacroAnalyzer()
        env = analyzer.classify_environment({
            "gdp_growth": 4.0,
            "inflation": 4.0,
            "rate_change": 0.0,
        })
        assert env == "GROWTH_INFLATION"

    def test_analyze_detailed(self):
        analyzer = MacroAnalyzer()
        details = analyzer.analyze_detailed({
            "gdp_growth": 3.0,
            "inflation": 2.5,
            "rate_change": 0.0,
            "yield_curve": 150,
            "credit_spread": 120,
        })
        assert details["environment"] == "GOLDILOCKS"
        assert "rate_stance" in details
        assert "inflation_stance" in details
        assert "curve_stance" in details
        assert "credit_stance" in details

    def test_to_macro_signal(self):
        analyzer = MacroAnalyzer()
        assert analyzer.to_macro_signal("GOLDILOCKS") == "RISK_ON"
        assert analyzer.to_macro_signal("RECOVERY") == "RISK_ON"
        assert analyzer.to_macro_signal("RECESSION") == "RISK_OFF"
        assert analyzer.to_macro_signal("STAGFLATION") == "RISK_OFF"

    def test_suggested_exposure(self):
        analyzer = MacroAnalyzer()
        assert analyzer.suggested_exposure("GOLDILOCKS") == 1.0
        assert analyzer.suggested_exposure("RECESSION") < 0.3

    def test_regime_favorable_strategies(self):
        analyzer = MacroAnalyzer()
        strategies = analyzer.regime_favorable_strategies("GOLDILOCKS")
        assert "momentum" in strategies
        strategies = analyzer.regime_favorable_strategies("RECESSION")
        assert "defensive" in strategies


# =============================================================================
# RegimeClassifier tests
# =============================================================================

class TestRegimeClassifier:
    """Test regime classifier."""

    def test_classify_legacy_interface(self):
        classifier = RegimeClassifier()
        result = classifier.classify({})
        assert result == "BULL_TREND"

    def test_classify_empty_inputs(self):
        classifier = RegimeClassifier()
        regime = classifier.classify_regime({})
        assert regime.state is not None
        assert isinstance(regime, MarketRegime)

    def test_classify_bull_low_vol(self):
        classifier = RegimeClassifier()
        data = {
            "price": 110,
            "ma_fast": 100,
            "ma_slow": 90,
            "ma_long": 80,
            "momentum": 8,
            "adx": 30,
            "vix": 14,
            "gdp_growth": 3.0,
            "inflation": 2.0,
            "rate_change": 0.0,
        }
        regime = classifier.classify_regime(data)
        assert regime.state is not None
        assert regime.confidence >= 0
        assert "BULL" in regime.state or "SIDEWAYS" in regime.state

    def test_classify_bear_high_vol(self):
        classifier = RegimeClassifier()
        data = {
            "price": 80,
            "ma_fast": 90,
            "ma_slow": 100,
            "ma_long": 110,
            "momentum": -10,
            "adx": 30,
            "vix": 32,
            "gdp_growth": -1.0,
            "inflation": 4.0,
        }
        regime = classifier.classify_regime(data)
        assert regime.state is not None

    def test_classify_with_evidence(self):
        classifier = RegimeClassifier()
        data = {
            "price": 105,
            "ma_fast": 100,
            "ma_slow": 95,
            "vix": 18,
            "gdp_growth": 3.0,
            "inflation": 2.0,
        }
        regime = classifier.classify_regime(data)
        assert len(regime.evidence) > 0

    def test_classify_with_previous_regime(self):
        classifier = RegimeClassifier()
        previous = MarketRegime(state="BULL_LOW_VOL", confidence=0.8)
        data = {
            "price": 80, "ma_fast": 90, "ma_slow": 100,
            "vix": 32, "gdp_growth": -1.0, "inflation": 4.0,
        }
        regime = classifier.classify_regime(data, previous_regime=previous)
        # Should detect transition from bull to bear
        assert regime.previous_state == "BULL_LOW_VOL"

    def test_classify_batch(self):
        classifier = RegimeClassifier()
        data_list = [
            {"price": 105, "ma_fast": 100, "ma_slow": 95, "vix": 14},
            {"price": 80, "ma_fast": 90, "ma_slow": 100, "vix": 32},
        ]
        regimes = classifier.classify_batch(data_list)
        assert len(regimes) == 2
        assert all(isinstance(r, MarketRegime) for r in regimes)

    def test_fuse_regimes_known(self):
        classifier = RegimeClassifier()
        result = classifier._fuse_regimes("BULL_TREND", "LOW")
        assert result == "BULL_LOW_VOL"

        result = classifier._fuse_regimes("BEAR_TREND", "HIGH")
        assert result == "BEAR_HIGH_VOL"

    def test_fuse_regimes_unknown(self):
        classifier = RegimeClassifier()
        result = classifier._fuse_regimes("UNKNOWN", "UNKNOWN")
        assert "_" in result  # falls back to "{trend}_{vol}"


# =============================================================================
# StrategyMatcher tests
# =============================================================================

class TestStrategyMatcher:
    """Test strategy matcher."""

    def test_match_legacy_interface(self):
        matcher = StrategyMatcher()
        result = matcher.match("BULL_TREND")
        assert result == "momentum"

    def test_match_default(self):
        matcher = StrategyMatcher()
        result = matcher.match("UNKNOWN_REGIME")
        assert result == "neutral"

    def test_match_strategies_bull_low_vol(self):
        matcher = StrategyMatcher()
        strategies = matcher.match_strategies("BULL_LOW_VOL")
        assert "momentum" in strategies
        assert "growth" in strategies

    def test_match_strategies_bear(self):
        matcher = StrategyMatcher()
        strategies = matcher.match_strategies("BEAR_TREND")
        assert "defensive" in strategies
        assert "safe_haven" in strategies or "inverse" in strategies

    def test_match_strategies_sideways(self):
        matcher = StrategyMatcher()
        strategies = matcher.match_strategies("SIDEWAYS")
        assert "mean_reversion" in strategies

    def test_match_strategies_crisis(self):
        matcher = StrategyMatcher()
        strategies = matcher.match_strategies("CRISIS")
        assert "safe_haven" in strategies

    def test_match_regime_full(self):
        matcher = StrategyMatcher()
        regime = MarketRegime(
            state="BULL_LOW_VOL",
            confidence=0.9,
            trend_signal="UPTREND",
            volatility_signal="LOW",
            macro_signal="RISK_ON",
        )
        result = matcher.match_regime(regime)
        assert "recommended_strategies" in result
        assert "suggested_exposure" in result
        assert "rationale" in result
        assert "warnings" in result

    def test_match_regime_with_warnings(self):
        matcher = StrategyMatcher()
        regime = MarketRegime(
            state="CRISIS",
            confidence=0.3,
            volatility_signal="EXTREME",
            macro_signal="RISK_OFF",
            transition_alert=True,
            transition_probability=0.8,
        )
        result = matcher.match_regime(regime)
        assert len(result["warnings"]) > 0

    def test_get_exposure(self):
        matcher = StrategyMatcher()
        assert matcher.get_exposure("BULL_LOW_VOL") == 1.0
        assert matcher.get_exposure("CRISIS") < 0.3
        assert matcher.get_exposure("BEAR_HIGH_VOL") < 0.5

    def test_get_strategy_weights(self):
        matcher = StrategyMatcher()
        weights = matcher.get_strategy_weights("BULL_LOW_VOL")
        assert len(weights) > 0
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.01

    def test_get_strategy_weights_unknown(self):
        matcher = StrategyMatcher()
        weights = matcher.get_strategy_weights("UNKNOWN")
        assert weights == {"neutral": 1.0}

    def test_macro_strategy_overlay(self):
        matcher = StrategyMatcher()
        regime = MarketRegime(
            state="BULL_LOW_VOL",
            macro_signal="RISK_ON",
        )
        strategies = matcher.macro_strategy_overlay(regime)
        assert len(strategies) > 0


# =============================================================================
# RegimeMemory tests
# =============================================================================

class TestRegimeMemory:
    """Test regime memory."""

    def test_save_regime(self):
        memory = RegimeMemory()
        regime = MarketRegime(state="BULL_TREND", confidence=0.85)
        record = memory.save(regime)
        assert record.regime_state == "BULL_TREND"
        assert record.confidence == 0.85

    def test_save_dict(self):
        memory = RegimeMemory()
        record = memory.save_dict({
            "state": "BEAR_TREND",
            "confidence": 0.7,
            "trend_signal": "DOWNTREND",
        })
        assert record.regime_state == "BEAR_TREND"

    def test_detect_transition(self):
        memory = RegimeMemory()
        memory.save(MarketRegime(state="BULL_TREND", confidence=0.8))
        memory.save(MarketRegime(state="BEAR_TREND", confidence=0.7))

        transitions = memory.get_transitions()
        assert len(transitions) == 1
        assert transitions[0].from_state == "BULL_TREND"
        assert transitions[0].to_state == "BEAR_TREND"

    def test_no_transition_on_same_state(self):
        memory = RegimeMemory()
        memory.save(MarketRegime(state="BULL_TREND"))
        memory.save(MarketRegime(state="BULL_TREND"))
        assert len(memory.get_transitions()) == 0

    def test_get_history(self):
        memory = RegimeMemory()
        memory.save(MarketRegime(state="BULL_TREND"))
        memory.save(MarketRegime(state="BEAR_TREND"))
        history = memory.get_history()
        assert len(history) == 2

    def test_get_recent(self):
        memory = RegimeMemory()
        for i in range(15):
            memory.save(MarketRegime(state=f"STATE_{i}"))
        recent = memory.get_recent(5)
        assert len(recent) == 5

    def test_get_latest(self):
        memory = RegimeMemory()
        assert memory.get_latest() is None
        memory.save(MarketRegime(state="BULL_TREND"))
        latest = memory.get_latest()
        assert latest.regime_state == "BULL_TREND"

    def test_get_by_state(self):
        memory = RegimeMemory()
        memory.save(MarketRegime(state="BULL_TREND"))
        memory.save(MarketRegime(state="BEAR_TREND"))
        memory.save(MarketRegime(state="BULL_TREND"))
        bull_records = memory.get_by_state("BULL_TREND")
        assert len(bull_records) == 2

    def test_regime_distribution(self):
        memory = RegimeMemory()
        memory.save(MarketRegime(state="BULL_TREND"))
        memory.save(MarketRegime(state="BULL_TREND"))
        memory.save(MarketRegime(state="BEAR_TREND"))
        dist = memory.regime_distribution()
        assert dist["BULL_TREND"] == 2
        assert dist["BEAR_TREND"] == 1

    def test_regime_duration(self):
        memory = RegimeMemory()
        memory.save(MarketRegime(state="BULL_TREND"))
        memory.save(MarketRegime(state="BULL_TREND"))
        memory.save(MarketRegime(state="BULL_TREND"))
        memory.save(MarketRegime(state="BEAR_TREND"))
        memory.save(MarketRegime(state="BULL_TREND"))
        duration = memory.regime_duration("BULL_TREND")
        assert duration > 0

    def test_transition_matrix(self):
        memory = RegimeMemory()
        memory.save(MarketRegime(state="BULL_TREND"))
        memory.save(MarketRegime(state="BEAR_TREND"))
        memory.save(MarketRegime(state="SIDEWAYS"))
        matrix = memory.transition_matrix()
        assert "BULL_TREND" in matrix
        assert "BEAR_TREND" in matrix

    def test_average_confidence(self):
        memory = RegimeMemory()
        memory.save(MarketRegime(state="BULL_TREND", confidence=0.8))
        memory.save(MarketRegime(state="BULL_TREND", confidence=0.6))
        avg = memory.average_confidence("BULL_TREND")
        assert avg == 0.7

    def test_summary(self):
        memory = RegimeMemory()
        memory.save(MarketRegime(state="BULL_TREND", confidence=0.9))
        summary = memory.summary()
        assert summary["total_observations"] == 1
        assert summary["current_regime"] == "BULL_TREND"

    def test_summary_empty(self):
        memory = RegimeMemory()
        summary = memory.summary()
        assert summary["total_observations"] == 0

    def test_reset(self):
        memory = RegimeMemory()
        memory.save(MarketRegime(state="BULL_TREND"))
        memory.reset()
        assert len(memory.get_records()) == 0
        assert len(memory.get_transitions()) == 0

    def test_get_transitions_between(self):
        memory = RegimeMemory()
        memory.save(MarketRegime(state="BULL_TREND"))
        memory.save(MarketRegime(state="BEAR_TREND"))
        memory.save(MarketRegime(state="BULL_TREND"))
        memory.save(MarketRegime(state="BEAR_TREND"))
        transitions = memory.get_transitions_between("BULL_TREND", "BEAR_TREND")
        assert len(transitions) == 2


# =============================================================================
# MarketRegimeService tests
# =============================================================================

class TestMarketRegimeService:
    """Test market regime service."""

    def test_analyze_legacy_interface(self):
        classifier = RegimeClassifier()
        service = MarketRegimeService(classifier)
        result = service.analyze({})
        assert result == "BULL_TREND"

    def test_detect_regime(self):
        service = MarketRegimeService()
        data = {
            "price": 110, "ma_fast": 100, "ma_slow": 90,
            "vix": 14, "gdp_growth": 3.0, "inflation": 2.0,
        }
        regime = service.detect_regime(data)
        assert isinstance(regime, MarketRegime)
        assert regime.state is not None

    def test_analyze_market(self):
        service = MarketRegimeService()
        data = {
            "price": 110, "ma_fast": 100, "ma_slow": 90,
            "vix": 14, "gdp_growth": 3.0, "inflation": 2.0,
        }
        result = service.analyze_market(data)
        assert "regime" in result
        assert "analysis" in result
        assert "recommendations" in result
        assert "transition_risk" in result
        assert len(result["recommendations"]["strategies"]) > 0

    def test_analyze_market_bear(self):
        service = MarketRegimeService()
        data = {
            "price": 80, "ma_fast": 90, "ma_slow": 100,
            "vix": 32, "gdp_growth": -1.0, "inflation": 4.0,
        }
        result = service.analyze_market(data)
        assert "analysis" in result

    def test_detect_trend(self):
        service = MarketRegimeService()
        data = {"price": 110, "ma_fast": 100, "ma_slow": 95, "adx": 30}
        result = service.detect_trend(data)
        assert "trend" in result
        assert "strength" in result

    def test_detect_volatility(self):
        service = MarketRegimeService()
        result = service.detect_volatility(vix=18, vol_change=5)
        assert "regime" in result
        assert "level" in result

    def test_analyze_macro(self):
        service = MarketRegimeService()
        result = service.analyze_macro({
            "gdp_growth": 3.0, "inflation": 2.0, "rate_change": 0.0,
        })
        assert "environment" in result
        assert "rate_stance" in result

    def test_get_recommended_strategies(self):
        service = MarketRegimeService()
        strategies = service.get_recommended_strategies("BULL_LOW_VOL")
        assert len(strategies) > 0
        assert "momentum" in strategies

    def test_get_strategy_allocation(self):
        service = MarketRegimeService()
        weights = service.get_strategy_allocation("BULL_LOW_VOL")
        assert len(weights) > 0

    def test_get_suggested_exposure(self):
        service = MarketRegimeService()
        exposure = service.get_suggested_exposure("BULL_LOW_VOL")
        assert exposure == 1.0
        exposure = service.get_suggested_exposure("CRISIS")
        assert exposure < 0.3

    def test_get_regime_history(self):
        service = MarketRegimeService()
        service.detect_regime({"price": 105, "ma_fast": 100, "ma_slow": 95})
        history = service.get_regime_history()
        assert len(history) >= 1

    def test_get_current_regime(self):
        service = MarketRegimeService()
        assert service.get_current_regime() is None
        service.detect_regime({"price": 105, "ma_fast": 100, "ma_slow": 95})
        current = service.get_current_regime()
        assert current is not None

    def test_get_transitions(self):
        service = MarketRegimeService()
        service.detect_regime({"price": 110, "ma_fast": 100, "ma_slow": 90, "vix": 14})
        service.detect_regime({"price": 80, "ma_fast": 90, "ma_slow": 100, "vix": 32})
        transitions = service.get_transitions()
        # May or may not have a transition depending on classification
        assert isinstance(transitions, list)

    def test_get_regime_summary(self):
        service = MarketRegimeService()
        service.detect_regime({"price": 110, "ma_fast": 100, "ma_slow": 90})
        summary = service.get_regime_summary()
        assert summary["total_observations"] >= 1

    def test_get_transition_matrix(self):
        service = MarketRegimeService()
        service.detect_regime({"price": 110, "ma_fast": 100, "ma_slow": 90, "vix": 14})
        service.detect_regime({"price": 80, "ma_fast": 90, "ma_slow": 100, "vix": 32})
        matrix = service.get_transition_matrix()
        assert isinstance(matrix, dict)

    def test_analyze_batch(self):
        service = MarketRegimeService()
        data_list = [
            {"price": 110, "ma_fast": 100, "ma_slow": 90, "vix": 14},
            {"price": 80, "ma_fast": 90, "ma_slow": 100, "vix": 32},
        ]
        results = service.analyze_batch(data_list)
        assert len(results) == 2

    def test_reset(self):
        service = MarketRegimeService()
        service.detect_regime({"price": 105, "ma_fast": 100, "ma_slow": 95})
        service.reset()
        assert service.get_current_regime() is None
        assert service.get_regime_summary()["total_observations"] == 0

    def test_full_workflow(self):
        """Integration test: full market regime workflow."""
        service = MarketRegimeService()

        # Step 1: Detect regime
        bull_data = {
            "price": 110, "ma_fast": 100, "ma_slow": 90, "ma_long": 80,
            "momentum": 8, "adx": 30, "vix": 14,
            "gdp_growth": 3.0, "inflation": 2.0, "rate_change": 0.0,
        }
        regime = service.detect_regime(bull_data)
        assert regime.state is not None
        assert isinstance(regime, MarketRegime)

        # Step 2: Get recommendations
        strategies = service.get_recommended_strategies(regime.state)
        assert len(strategies) > 0

        # Step 3: Get allocation
        weights = service.get_strategy_allocation(regime.state)
        assert len(weights) > 0

        # Step 4: Check history
        history = service.get_regime_history()
        assert len(history) >= 1

    def test_end_to_end_regime_analysis(self):
        """End-to-end test: data → analyze → recommendations."""
        service = MarketRegimeService()

        # Full market analysis
        result = service.analyze_market({
            "price": 110,
            "ma_fast": 100,
            "ma_slow": 90,
            "ma_long": 80,
            "momentum": 8,
            "adx": 30,
            "breadth": 1.8,
            "vix": 14,
            "historical_vol": 12,
            "vol_percentile": 20,
            "vol_change": -3,
            "gdp_growth": 3.0,
            "inflation": 2.0,
            "interest_rate": 4.5,
            "rate_change": 0.0,
            "yield_curve": 120,
            "credit_spread": 100,
        })

        # Verify structure
        assert result["analysis"]["is_bull"] is True or result["analysis"]["is_sideways"] is True
        assert len(result["recommendations"]["strategies"]) > 0
        assert result["recommendations"]["suggested_exposure"] > 0


# =============================================================================
# RegimeRecord tests
# =============================================================================

class TestRegimeRecord:
    """Test RegimeRecord."""

    def test_create_record(self):
        record = RegimeRecord(
            record_id="REG-000001",
            regime_state="BULL_TREND",
            confidence=0.9,
        )
        assert record.record_id == "REG-000001"
        assert record.regime_state == "BULL_TREND"

    def test_to_dict(self):
        record = RegimeRecord(
            regime_state="BEAR_TREND",
            confidence=0.7,
            trend_signal="DOWNTREND",
            recommended_strategies=["defensive"],
            suggested_exposure=0.3,
        )
        d = record.to_dict()
        assert d["regime_state"] == "BEAR_TREND"
        assert d["recommended_strategies"] == ["defensive"]


# =============================================================================
# Edge cases
# =============================================================================

class TestEdgeCases:
    """Edge case tests."""

    def test_classifier_empty_dict(self):
        classifier = RegimeClassifier()
        regime = classifier.classify_regime({})
        assert regime.state is not None

    def test_detect_trend_empty(self):
        detector = TrendDetector()
        trend = detector.classify_trend({})
        assert trend == "NEUTRAL"

    def test_detect_volatility_no_input(self):
        detector = VolatilityDetector()
        regime = detector.classify_volatility()
        assert regime == "NORMAL"

    def test_analyze_macro_empty(self):
        analyzer = MacroAnalyzer()
        env = analyzer.classify_environment({})
        assert env == "GOLDILOCKS"

    def test_memory_empty_queries(self):
        memory = RegimeMemory()
        assert memory.get_latest() is None
        assert memory.get_recent(10) == []
        assert memory.regime_duration("BULL") == 0.0
        assert memory.average_confidence() == 0.0

    def test_service_reset_preserves_classifier(self):
        classifier = RegimeClassifier()
        service = MarketRegimeService(classifier)
        assert service.classifier is classifier
        service.reset()
        assert service.classifier is classifier  # classifier not reset

    def test_custom_thresholds(self):
        detector = VolatilityDetector(vix_low=12, vix_elevated=22, vix_high=28)
        assert detector.detect(30) == "HIGH"

    def test_regime_transition_edge(self):
        """Test rapid regime transitions."""
        memory = RegimeMemory()
        states = ["BULL_TREND", "BEAR_TREND", "BULL_TREND", "BEAR_TREND", "SIDEWAYS"]
        for s in states:
            memory.save(MarketRegime(state=s))
        transitions = memory.get_transitions()
        assert len(transitions) == 4  # one per state change

    def test_batch_classification_no_previous(self):
        classifier = RegimeClassifier()
        regimes = classifier.classify_batch([{}, {}])
        assert len(regimes) == 2

    def test_strategy_weights_sum_to_one(self):
        matcher = StrategyMatcher()
        for state in ["BULL_LOW_VOL", "BEAR_HIGH_VOL", "SIDEWAYS", "CRISIS"]:
            weights = matcher.get_strategy_weights(state)
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.05, f"{state}: weights sum to {total}"
