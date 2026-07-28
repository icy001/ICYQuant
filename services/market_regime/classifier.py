"""Regime Classifier – fuse multi-dimensional signals into a unified regime."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from .macro import MacroAnalyzer
from .regime import MarketRegime, RegimeState
from .trend import TrendDetector
from .volatility import VolatilityDetector


class RegimeClassifier:
    """Fuses trend, volatility, and macro signals into a unified market regime.

    The classifier combines:
    - Trend detection (direction + strength)
    - Volatility analysis (level + trend)
    - Macro environment analysis

    to produce a single MarketRegime classification with confidence scores.
    """

    # Composite regime mapping
    COMPOSITE_REGIMES = {
        # (trend_regime, volatility_regime) → composite_state
        ("BULL_TREND", "EXTREMELY_LOW"): RegimeState.BULL_LOW_VOL,
        ("BULL_TREND", "LOW"): RegimeState.BULL_LOW_VOL,
        ("BULL_TREND", "NORMAL"): RegimeState.BULL_LOW_VOL,
        ("BULL_TREND", "ELEVATED"): RegimeState.BULL_HIGH_VOL,
        ("BULL_TREND", "HIGH"): RegimeState.BULL_HIGH_VOL,
        ("BULL_TREND", "EXTREME"): RegimeState.BULL_HIGH_VOL,
        ("BEAR_TREND", "EXTREMELY_LOW"): RegimeState.BEAR_LOW_VOL,
        ("BEAR_TREND", "LOW"): RegimeState.BEAR_LOW_VOL,
        ("BEAR_TREND", "NORMAL"): RegimeState.BEAR_LOW_VOL,
        ("BEAR_TREND", "ELEVATED"): RegimeState.BEAR_HIGH_VOL,
        ("BEAR_TREND", "HIGH"): RegimeState.BEAR_HIGH_VOL,
        ("BEAR_TREND", "EXTREME"): RegimeState.BEAR_HIGH_VOL,
        ("SIDEWAYS", "EXTREMELY_LOW"): RegimeState.SIDEWAYS_LOW_VOL,
        ("SIDEWAYS", "LOW"): RegimeState.SIDEWAYS_LOW_VOL,
        ("SIDEWAYS", "NORMAL"): RegimeState.SIDEWAYS_LOW_VOL,
        ("SIDEWAYS", "ELEVATED"): RegimeState.SIDEWAYS_HIGH_VOL,
        ("SIDEWAYS", "HIGH"): RegimeState.SIDEWAYS_HIGH_VOL,
        ("SIDEWAYS", "EXTREME"): RegimeState.SIDEWAYS_HIGH_VOL,
    }

    def __init__(self,
                 trend_detector: Optional[TrendDetector] = None,
                 volatility_detector: Optional[VolatilityDetector] = None,
                 macro_analyzer: Optional[MacroAnalyzer] = None):
        self.trend = trend_detector or TrendDetector()
        self.volatility = volatility_detector or VolatilityDetector()
        self.macro = macro_analyzer or MacroAnalyzer()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(self, inputs: dict) -> str:
        """Classify regime from input data (legacy interface).

        Returns regime state string.
        """
        if not inputs:
            return "BULL_TREND"

        regime = self.classify_regime(inputs)
        return regime.state

    def classify_regime(self, data: dict,
                        previous_regime: Optional[MarketRegime] = None
                        ) -> MarketRegime:
        """Classify the current market regime from all available data.

        Args:
            data: dict with market data containing:
                - Market data for trend detection (price, ma_fast, etc.)
                - Market data for volatility (vix, historical_vol, etc.)
                - Market data for macro (gdp_growth, inflation, etc.)
            previous_regime: Previous regime for transition detection

        Returns:
            MarketRegime with full classification details
        """
        # 1. Trend detection
        trend_signal = self.trend.classify_trend(data)
        trend_strength = self.trend.trend_strength(data)
        trend_regime = self.trend.to_regime(trend_signal)

        # 2. Volatility detection
        vix = data.get("vix")
        historical_vol = data.get("historical_vol")
        vol_percentile = data.get("vol_percentile")
        vol_change = data.get("vol_change")

        vol_signal = self.volatility.classify_volatility(
            vix=vix, historical_vol=historical_vol,
            vol_percentile=vol_percentile, vol_change=vol_change,
        )
        vol_level = self.volatility.volatility_level(vix=vix, historical_vol=historical_vol)

        # 3. Macro analysis
        macro_signal = self.macro.classify_environment(data)
        macro_detail = self.macro.analyze_detailed(data)

        # 4. Fuse into composite regime
        composite_state = self._fuse_regimes(trend_regime, vol_signal)

        # 5. Compute confidence
        trend_detail = self.trend.detect_with_details(data)
        vol_detail = self.volatility.detect_with_details(
            vix=vix, historical_vol=historical_vol,
            vol_percentile=vol_percentile, vol_change=vol_change,
        )

        confidence = self._compute_confidence(
            trend_detail["confidence"],
            vol_signal,
            macro_signal,
        )

        # 6. Build evidence
        evidence = self._build_evidence(
            trend_signal, trend_strength, vol_signal, vol_level, macro_signal
        )

        # 7. Check for transitions
        transition_alert = False
        transition_prob = 0.0
        previous_state = ""
        if previous_regime is not None:
            previous_state = previous_regime.state
            if previous_state != composite_state:
                transition_alert = True
                transition_prob = round(1.0 - confidence, 2)

        # 8. Build regime
        regime = MarketRegime(
            state=composite_state,
            confidence=round(confidence, 2),
            confidence_breakdown={
                "trend": trend_detail["confidence"],
                "volatility": 0.8 if vol_signal else 0.5,
                "macro": 0.7 if macro_signal else 0.5,
            },
            timestamp=datetime.now(),
            period=data.get("period", "1d"),
            trend_signal=trend_signal,
            trend_strength=trend_strength,
            volatility_signal=vol_signal,
            volatility_level=vol_level,
            macro_signal=macro_signal,
            features={
                "vix": vix,
                "historical_vol": historical_vol,
                "trend_detail": trend_detail,
                "vol_detail": vol_detail,
                "macro_detail": macro_detail,
            },
            evidence=evidence,
            previous_state=previous_state,
            transition_alert=transition_alert,
            transition_probability=transition_prob,
        )

        return regime

    def classify_batch(self, data_list: List[dict]) -> List[MarketRegime]:
        """Classify multiple data points."""
        regimes = []
        previous = None
        for data in data_list:
            regime = self.classify_regime(data, previous_regime=previous)
            regimes.append(regime)
            previous = regime
        return regimes

    # ------------------------------------------------------------------
    # Fusion logic
    # ------------------------------------------------------------------

    def _fuse_regimes(self, trend_regime: str, vol_signal: str) -> str:
        """Fuse trend and volatility signals into a composite regime."""
        key = (trend_regime, vol_signal)
        return self.COMPOSITE_REGIMES.get(key, f"{trend_regime}_{vol_signal}")

    def _compute_confidence(self, trend_conf: float,
                            vol_signal: str, macro_signal: str) -> float:
        """Compute overall confidence from sub-signals."""
        # Base: trend confidence
        conf = trend_conf * 0.5

        # Volatility clarity (strong signals = higher confidence)
        vol_weight = 0.3
        vol_clarity = {
            VolatilityDetector.EXTREME: 0.9,
            VolatilityDetector.HIGH: 0.85,
            VolatilityDetector.ELEVATED: 0.7,
            VolatilityDetector.NORMAL: 0.6,
            VolatilityDetector.LOW: 0.7,
            VolatilityDetector.EXTREMELY_LOW: 0.8,
        }
        conf += vol_clarity.get(vol_signal, 0.5) * vol_weight

        # Macro signal weight
        macro_weight = 0.2
        if macro_signal:
            conf += 0.7 * macro_weight
        else:
            conf += 0.4 * macro_weight

        return min(1.0, max(0.0, conf))

    def _build_evidence(self, trend: str, trend_strength: float,
                        vol: str, vol_level: float,
                        macro_env: str) -> List[str]:
        """Build human-readable evidence list."""
        evidence = []

        if "UPTREND" in trend:
            evidence.append(f"Trend: {trend} (strength={trend_strength:.2f})")
        elif "DOWNTREND" in trend:
            evidence.append(f"Trend: {trend} (strength={trend_strength:.2f})")
        else:
            evidence.append(f"Trend: {trend}")

        evidence.append(f"Volatility: {vol} (level={vol_level:.2f})")

        if macro_env:
            evidence.append(f"Macro: {macro_env}")

        return evidence
