"""Strategy Regime Matcher – match strategies to market regimes."""

from typing import Any, Dict, List, Optional

from .macro import MacroAnalyzer
from .regime import MarketRegime, RegimeState


class StrategyMatcher:
    """Matches optimal strategies to the current market regime.

    Connects the Strategy Evolution Engine with Market Regime Intelligence:
    based on the detected regime, recommends which strategy types to deploy.

    Also provides adaptive portfolio exposure adjustments based on regime.
    """

    # Regime → preferred strategy types mapping
    REGIME_STRATEGY_MAP: Dict[str, List[str]] = {
        # Bull markets → momentum, growth, trend-following
        RegimeState.BULL_LOW_VOL: ["momentum", "growth", "breakout", "trend_following"],
        RegimeState.BULL_HIGH_VOL: ["momentum", "swing_trading", "breakout"],
        RegimeState.BULL_TREND: ["momentum", "growth", "breakout", "trend_following"],

        # Bear markets → defensive, inverse, short-biased
        RegimeState.BEAR_LOW_VOL: ["defensive", "value", "dividend", "low_volatility"],
        RegimeState.BEAR_HIGH_VOL: ["inverse", "safe_haven", "volatility", "defensive"],
        RegimeState.BEAR_TREND: ["inverse", "safe_haven", "defensive", "low_volatility"],

        # Sideways → mean reversion, market neutral, range trading
        RegimeState.SIDEWAYS_LOW_VOL: ["mean_reversion", "range_trading", "options_income"],
        RegimeState.SIDEWAYS_HIGH_VOL: ["mean_reversion", "market_neutral", "stat_arb"],
        RegimeState.SIDEWAYS: ["mean_reversion", "range_trading", "market_neutral"],

        # Crisis → extreme defensive
        RegimeState.CRISIS: ["safe_haven", "tail_hedge", "inverse", "gold"],
    }

    # Regime → suggested equity exposure (0.0 - 1.0)
    REGIME_EXPOSURE_MAP: Dict[str, float] = {
        RegimeState.BULL_LOW_VOL: 1.0,
        RegimeState.BULL_HIGH_VOL: 0.8,
        RegimeState.BULL_TREND: 1.0,
        RegimeState.BEAR_LOW_VOL: 0.4,
        RegimeState.BEAR_HIGH_VOL: 0.2,
        RegimeState.BEAR_TREND: 0.3,
        RegimeState.SIDEWAYS_LOW_VOL: 0.7,
        RegimeState.SIDEWAYS_HIGH_VOL: 0.5,
        RegimeState.SIDEWAYS: 0.6,
        RegimeState.CRISIS: 0.1,
    }

    def __init__(self):
        self._macro_analyzer = MacroAnalyzer()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def match(self, regime: str) -> str:
        """Match a regime to the best strategy type (legacy interface).

        Returns a single strategy type string.
        """
        strategies = self.match_strategies(regime)
        return strategies[0] if strategies else "Neutral"

    def match_strategies(self, regime: str) -> List[str]:
        """Get recommended strategy types for a regime.

        Args:
            regime: Regime state string (e.g., "BULL_LOW_VOL", "BULL_TREND")

        Returns:
            List of recommended strategy types, ordered by preference
        """
        return self.REGIME_STRATEGY_MAP.get(regime, ["neutral"])

    def match_regime(self, regime: MarketRegime) -> dict:
        """Comprehensive regime matching for a MarketRegime object.

        Returns:
            dict with recommended strategies, exposure, and rationale
        """
        strategies = self.match_strategies(regime.state)
        exposure = self.get_exposure(regime.state)

        # Adjust exposure by confidence
        adjusted_exposure = round(exposure * regime.confidence, 2)

        # Build rationale
        rationale = self._build_rationale(regime)

        return {
            "regime": regime.state,
            "confidence": regime.confidence,
            "recommended_strategies": strategies,
            "suggested_exposure": adjusted_exposure,
            "base_exposure": exposure,
            "rationale": rationale,
            "warnings": self._get_warnings(regime),
        }

    def get_exposure(self, regime: str) -> float:
        """Get suggested equity exposure for a regime."""
        return self.REGIME_EXPOSURE_MAP.get(regime, 0.6)

    def get_strategy_weights(self, regime: str) -> Dict[str, float]:
        """Get strategy allocation weights for a regime.

        Distributes 100% across recommended strategies, with the first
        strategy getting the highest weight.
        """
        strategies = self.match_strategies(regime)
        n = len(strategies)
        if n == 0:
            return {"neutral": 1.0}

        weights = {}
        remaining = 1.0
        for i, s in enumerate(strategies):
            if i == n - 1:
                weights[s] = round(remaining, 2)
            else:
                w = round(0.6 * remaining, 2) if i == 0 else round(0.4 * remaining, 2)
                weights[s] = w
                remaining -= w

        return weights

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_rationale(self, regime: MarketRegime) -> List[str]:
        """Build rationale for strategy recommendations."""
        rationale = []

        if regime.is_bull:
            rationale.append("Bull market favors momentum and growth strategies")
        elif regime.is_bear:
            rationale.append("Bear market calls for defensive positioning")
        elif regime.is_sideways:
            rationale.append("Sideways market suits mean reversion approaches")

        if regime.is_high_volatility:
            rationale.append("Elevated volatility requires reduced position sizing")
        elif regime.is_low_volatility:
            rationale.append("Low volatility allows higher conviction positions")

        if regime.is_risk_off:
            rationale.append("Risk-off macro environment: reduce risk exposure")
        elif regime.is_risk_on:
            rationale.append("Risk-on macro environment supports equity exposure")

        return rationale

    def _get_warnings(self, regime: MarketRegime) -> List[str]:
        """Generate warnings based on regime conditions."""
        warnings = []

        if regime.is_crisis:
            warnings.append("CRISIS MODE: Extreme caution required")
        if regime.is_high_volatility and regime.is_bear:
            warnings.append("High volatility bear market: consider hedging")
        if regime.transition_alert:
            warnings.append(
                f"Regime transition in progress (prob: {regime.transition_probability:.0%})"
            )
        if regime.confidence < 0.5:
            warnings.append("Low confidence regime: reduce position sizes")

        return warnings

    def macro_strategy_overlay(self, regime: MarketRegime) -> List[str]:
        """Add macro-driven strategy suggestions on top of regime matching."""
        base = self.match_strategies(regime.state)
        macro_env = regime.macro_signal

        macro_strategies = self._macro_analyzer.regime_favorable_strategies(macro_env)

        # Combine, deduplicate, prioritize base strategies
        combined = list(base)
        for ms in macro_strategies:
            if ms not in combined:
                combined.append(ms)

        return combined
