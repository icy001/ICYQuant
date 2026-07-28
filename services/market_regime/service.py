"""Market Regime Intelligence Service – unified API for regime detection and adaptation."""

from typing import Any, Dict, List, Optional

from .classifier import RegimeClassifier
from .macro import MacroAnalyzer
from .matcher import StrategyMatcher
from .memory import RegimeMemory
from .regime import MarketRegime, RegimeState, RegimeTransition
from .trend import TrendDetector
from .volatility import VolatilityDetector


class MarketRegimeService:
    """Unified service for AI Market Regime Intelligence.

    Orchestrates:
    - Market regime detection (trend + volatility + macro)
    - Strategy matching (which strategies fit the current regime)
    - Adaptive exposure recommendations
    - Regime memory (historical tracking)
    - Transition monitoring and alerts
    """

    def __init__(
        self,
        classifier: Optional[RegimeClassifier] = None,
        matcher: Optional[StrategyMatcher] = None,
        memory: Optional[RegimeMemory] = None,
        trend_detector: Optional[TrendDetector] = None,
        volatility_detector: Optional[VolatilityDetector] = None,
        macro_analyzer: Optional[MacroAnalyzer] = None,
    ):
        self.classifier = classifier or RegimeClassifier()
        self.matcher = matcher or StrategyMatcher()
        self.memory = memory or RegimeMemory()

        # Expose sub-components for direct access
        self.trend = trend_detector or self.classifier.trend
        self.volatility = volatility_detector or self.classifier.volatility
        self.macro = macro_analyzer or self.classifier.macro

    # ------------------------------------------------------------------
    # Legacy API
    # ------------------------------------------------------------------

    def analyze(self, data: dict) -> str:
        """Analyze market and return regime state (legacy interface).

        Returns regime state string for backward compatibility.
        """
        return self.classifier.classify(data)

    # ------------------------------------------------------------------
    # Core regime detection
    # ------------------------------------------------------------------

    def detect_regime(self, market_data: dict) -> MarketRegime:
        """Detect the current market regime from market data.

        Args:
            market_data: dict with market indicators:
                - Price/trend data: price, ma_fast, ma_slow, ma_long,
                  momentum, adx, breadth, consecutive_up, consecutive_down
                - Volatility data: vix, historical_vol, vol_percentile, vol_change
                - Macro data: gdp_growth, inflation, interest_rate, rate_change,
                  yield_curve, credit_spread, etc.

        Returns:
            MarketRegime with full classification
        """
        # Get previous regime for transition detection
        previous = self._get_previous_regime()

        # Classify
        regime = self.classifier.classify_regime(market_data, previous_regime=previous)

        # Match strategies
        match_result = self.matcher.match_regime(regime)
        regime.recommended_strategies = match_result["recommended_strategies"]
        regime.suggested_exposure = match_result["suggested_exposure"]

        # Save to memory
        self.memory.save(regime)

        return regime

    def analyze_market(self, market_data: dict) -> dict:
        """Full market analysis with regime + recommendations.

        Returns comprehensive analysis dict suitable for downstream consumers.
        """
        regime = self.detect_regime(market_data)
        match_result = self.matcher.match_regime(regime)
        strategy_weights = self.matcher.get_strategy_weights(regime.state)

        # Macro overlay
        macro_overlay_strategies = self.matcher.macro_strategy_overlay(regime)

        # Transition analysis
        transition_risk = self._assess_transition_risk(regime)

        return {
            "regime": regime.to_dict(),
            "analysis": {
                "summary": regime.summary(),
                "is_bull": regime.is_bull,
                "is_bear": regime.is_bear,
                "is_sideways": regime.is_sideways,
                "is_high_volatility": regime.is_high_volatility,
                "is_crisis": regime.is_crisis,
                "is_risk_on": regime.is_risk_on,
            },
            "recommendations": {
                "strategies": match_result["recommended_strategies"],
                "strategy_weights": strategy_weights,
                "macro_overlay_strategies": macro_overlay_strategies,
                "suggested_exposure": match_result["suggested_exposure"],
                "base_exposure": match_result["base_exposure"],
                "rationale": match_result["rationale"],
                "warnings": match_result["warnings"],
            },
            "transition_risk": transition_risk,
        }

    # ------------------------------------------------------------------
    # Trend, Volatility, Macro (direct access)
    # ------------------------------------------------------------------

    def detect_trend(self, data: dict) -> dict:
        """Direct trend detection."""
        return self.trend.detect_with_details(data)

    def detect_volatility(self, vix: Optional[float] = None,
                          historical_vol: Optional[float] = None,
                          vol_percentile: Optional[float] = None,
                          vol_change: Optional[float] = None) -> dict:
        """Direct volatility detection."""
        return self.volatility.detect_with_details(
            vix=vix, historical_vol=historical_vol,
            vol_percentile=vol_percentile, vol_change=vol_change,
        )

    def analyze_macro(self, macro_data: dict) -> dict:
        """Direct macro environment analysis."""
        return self.macro.analyze_detailed(macro_data)

    # ------------------------------------------------------------------
    # Strategy adaptation
    # ------------------------------------------------------------------

    def get_recommended_strategies(self, regime_state: str) -> List[str]:
        """Get recommended strategies for a regime state."""
        return self.matcher.match_strategies(regime_state)

    def get_strategy_allocation(self, regime_state: str) -> Dict[str, float]:
        """Get strategy allocation weights for a regime."""
        return self.matcher.get_strategy_weights(regime_state)

    def get_suggested_exposure(self, regime_state: str) -> float:
        """Get suggested equity exposure for a regime."""
        return self.matcher.get_exposure(regime_state)

    # ------------------------------------------------------------------
    # Regime memory & history
    # ------------------------------------------------------------------

    def get_regime_history(self) -> List[dict]:
        """Get historical regime observations."""
        return self.memory.get_history()

    def get_current_regime(self) -> Optional[dict]:
        """Get the most recent regime observation."""
        latest = self.memory.get_latest()
        return latest.to_dict() if latest else None

    def get_transitions(self) -> List[dict]:
        """Get regime transition history."""
        return [t.to_dict() for t in self.memory.get_transitions()]

    def get_regime_summary(self) -> dict:
        """Get regime memory summary."""
        return self.memory.summary()

    def get_transition_matrix(self) -> dict:
        """Get regime transition matrix."""
        return self.memory.transition_matrix()

    # ------------------------------------------------------------------
    # Batch processing
    # ------------------------------------------------------------------

    def analyze_batch(self, data_list: List[dict]) -> List[dict]:
        """Analyze a batch of market data points."""
        results = []
        for data in data_list:
            result = self.analyze_market(data)
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_previous_regime(self) -> Optional[MarketRegime]:
        """Reconstruct previous MarketRegime from memory for transition detection."""
        latest_record = self.memory.get_latest()
        if latest_record is None:
            return None

        # Build a minimal MarketRegime from the latest record
        return MarketRegime(
            state=latest_record.regime_state,
            confidence=latest_record.confidence,
            trend_signal=latest_record.trend_signal,
            volatility_signal=latest_record.volatility_signal,
            macro_signal=latest_record.macro_signal,
        )

    def _assess_transition_risk(self, regime: MarketRegime) -> dict:
        """Assess risk of regime transition."""
        if not regime.transition_alert:
            return {"risk_level": "low", "probability": 0.0, "message": "Regime stable"}

        prob = regime.transition_probability
        if prob > 0.7:
            level = "high"
            msg = f"High probability ({prob:.0%}) of regime change"
        elif prob > 0.4:
            level = "medium"
            msg = f"Moderate probability ({prob:.0%}) of regime change"
        else:
            level = "low"
            msg = f"Low probability ({prob:.0%}) of regime change"

        return {
            "risk_level": level,
            "probability": prob,
            "message": msg,
            "from_state": regime.previous_state,
            "to_state": regime.state,
        }

    def reset(self) -> None:
        """Reset the service state."""
        self.memory.reset()
