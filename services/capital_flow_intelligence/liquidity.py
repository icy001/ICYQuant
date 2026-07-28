"""Liquidity Movement Predictor.

Predicts liquidity environment conditions by analyzing money supply,
bond yields, dollar strength, credit spreads, and central bank operations
to forecast capital availability for risk assets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .record import LiquidityRegime


@dataclass
class LiquidityResult:
    """Result of liquidity prediction.

    Attributes:
        regime: Predicted liquidity regime.
        score: Composite liquidity score [0, 100] (higher = more liquid).
        confidence: Prediction confidence [0.0, 1.0].
        components: Individual component scores.
        trend: Liquidity trend direction.
        description: Human-readable summary.
        risk_level: Associated risk level [0.0, 1.0].
        timestamp: Prediction timestamp.
    """

    regime: LiquidityRegime = LiquidityRegime.NEUTRAL
    score: float = 50.0
    confidence: float = 0.5
    components: dict[str, dict[str, Any]] = field(default_factory=dict)
    trend: str = "stable"
    description: str = ""
    risk_level: float = 0.5
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_expanding(self) -> bool:
        return self.regime in (LiquidityRegime.ABUNDANT, LiquidityRegime.EXPANDING)

    @property
    def is_contracting(self) -> bool:
        return self.regime in (LiquidityRegime.CONTRACTING, LiquidityRegime.TIGHT, LiquidityRegime.CRISIS)

    @property
    def is_risk_on(self) -> bool:
        return self.score >= 60.0

    @property
    def is_risk_off(self) -> bool:
        return self.score <= 40.0


class LiquidityPredictor:
    """Predicts liquidity environment by analyzing macro indicators.

    Uses money supply, bond yields, dollar index, credit spreads,
    and central bank policy to forecast liquidity conditions for
    risk asset allocation decisions.

    Attributes:
        weights: Component weights for liquidity scoring.
        score_history: Rolling history of liquidity scores.
        regime_history: History of regime changes.
    """

    def __init__(self) -> None:
        self.weights: dict[str, float] = {
            "money_supply": 0.25,
            "bond_yield": 0.20,
            "dollar": 0.20,
            "credit_spread": 0.20,
            "cb_policy": 0.15,
        }
        self.score_history: list[float] = []
        self.regime_history: list[LiquidityRegime] = []

    # --- Prediction ---

    def predict(self, data: dict[str, float] | None = None) -> str:
        """Predict liquidity regime label.

        Args:
            data: Dict of component values [0, 100].
                  Keys: money_supply, bond_yield, dollar, credit_spread, cb_policy.

        Returns:
            Liquidity regime string value.
        """
        if not data:
            return "NEUTRAL"

        score = self._compute_score(data)
        regime = self._score_to_regime(score)
        return regime.value.upper()

    def analyze(self, data: dict[str, float] | None = None) -> LiquidityResult:
        """Full liquidity analysis with regime and trend.

        Args:
            data: Dict of component values [0, 100].

        Returns:
            LiquidityResult with comprehensive analysis.
        """
        if not data:
            return LiquidityResult(description="No data for liquidity analysis.")

        score = self._compute_score(data)
        regime = self._score_to_regime(score)
        self.score_history.append(score)
        self.regime_history.append(regime)

        if len(self.score_history) > 200:
            self.score_history = self.score_history[-200:]

        # Component details
        components: dict[str, dict[str, Any]] = {}
        for name in self.weights:
            if name in data:
                components[name] = {
                    "value": data[name],
                    "weight": self.weights[name],
                    "contribution": data[name] * self.weights[name],
                }

        # Trend
        trend = self._compute_trend()

        # Confidence
        confidence = self._compute_confidence(data, score)

        # Risk level
        risk_level = self._compute_risk_level(regime)

        # Description
        description = self._generate_description(regime, score, trend)

        return LiquidityResult(
            regime=regime,
            score=score,
            confidence=confidence,
            components=components,
            trend=trend,
            description=description,
            risk_level=risk_level,
        )

    def analyze_from_components(
        self,
        money_supply: float | None = None,
        bond_yield: float | None = None,
        dollar: float | None = None,
        credit_spread: float | None = None,
        cb_policy: float | None = None,
    ) -> LiquidityResult:
        """Predict liquidity from individual component values.

        Each component on 0-100 scale where higher = more liquid:
        - money_supply: Money supply growth signal
        - bond_yield: Inverted: lower yield = more liquidity
        - dollar: Inverted: weaker dollar = more liquidity
        - credit_spread: Inverted: tighter spreads = more liquidity
        - cb_policy: Central bank policy stance (dovish=high)

        Returns:
            LiquidityResult.
        """
        data: dict[str, float] = {}
        if money_supply is not None:
            data["money_supply"] = max(0.0, min(100.0, money_supply))
        if bond_yield is not None:
            data["bond_yield"] = max(0.0, min(100.0, bond_yield))
        if dollar is not None:
            data["dollar"] = max(0.0, min(100.0, dollar))
        if credit_spread is not None:
            data["credit_spread"] = max(0.0, min(100.0, credit_spread))
        if cb_policy is not None:
            data["cb_policy"] = max(0.0, min(100.0, cb_policy))
        return self.analyze(data) if data else LiquidityResult()

    # --- Analysis Helpers ---

    def get_trend(self, window: int = 10) -> str:
        """Get liquidity score trend over recent history."""
        if len(self.score_history) < 2:
            return "stable"
        recent = self.score_history[-window:]
        if len(recent) < 2:
            return "stable"
        mid = len(recent) // 2
        first = sum(recent[:mid]) / mid
        second = sum(recent[mid:]) / (len(recent) - mid)
        diff = second - first
        if diff > 5:
            return "rising"
        elif diff < -5:
            return "falling"
        return "stable"

    def get_risk_asset_outlook(self) -> str:
        """Get risk asset allocation outlook based on liquidity.

        Returns:
            'favorable', 'cautious', or 'unfavorable'.
        """
        if not self.score_history:
            return "neutral"
        score = self.score_history[-1]
        if score >= 65:
            return "favorable"
        elif score <= 35:
            return "unfavorable"
        return "cautious"

    # --- Internal ---

    def _compute_score(self, data: dict[str, float]) -> float:
        """Compute weighted liquidity score from component data."""
        weighted_sum = 0.0
        total_weight = 0.0
        for component, weight in self.weights.items():
            if component in data:
                value = max(0.0, min(100.0, data[component]))
                weighted_sum += value * weight
                total_weight += weight
        if total_weight == 0:
            return 50.0
        return weighted_sum / total_weight

    def _score_to_regime(self, score: float) -> LiquidityRegime:
        """Map liquidity score to regime."""
        if score >= 80:
            return LiquidityRegime.ABUNDANT
        elif score >= 65:
            return LiquidityRegime.EXPANDING
        elif score >= 45:
            return LiquidityRegime.NEUTRAL
        elif score >= 30:
            return LiquidityRegime.CONTRACTING
        elif score >= 15:
            return LiquidityRegime.TIGHT
        else:
            return LiquidityRegime.CRISIS

    def _compute_trend(self) -> str:
        """Compute current liquidity trend."""
        return self.get_trend()

    def _compute_confidence(self, data: dict[str, float], score: float) -> float:
        """Compute prediction confidence."""
        confidence = 0.3

        # More components = higher confidence
        provided = sum(1 for c in self.weights if c in data)
        confidence += 0.1 * min(1.0, provided / 5.0)

        # Extreme scores = higher confidence
        if abs(score - 50.0) > 30:
            confidence += 0.3
        elif abs(score - 50.0) > 15:
            confidence += 0.15

        # History length increases confidence
        if len(self.score_history) > 10:
            confidence += 0.1

        return min(1.0, confidence)

    def _compute_risk_level(self, regime: LiquidityRegime) -> float:
        """Compute risk level from liquidity regime."""
        risk_map = {
            LiquidityRegime.ABUNDANT: 0.2,
            LiquidityRegime.EXPANDING: 0.35,
            LiquidityRegime.NEUTRAL: 0.5,
            LiquidityRegime.CONTRACTING: 0.65,
            LiquidityRegime.TIGHT: 0.8,
            LiquidityRegime.CRISIS: 0.95,
        }
        return risk_map.get(regime, 0.5)

    def _generate_description(
        self, regime: LiquidityRegime, score: float, trend: str
    ) -> str:
        """Generate human-readable description."""
        desc_map = {
            LiquidityRegime.ABUNDANT: "Ample liquidity - highly supportive of risk assets",
            LiquidityRegime.EXPANDING: "Liquidity expanding - favorable for equities",
            LiquidityRegime.NEUTRAL: "Liquidity neutral - balanced conditions",
            LiquidityRegime.CONTRACTING: "Liquidity contracting - caution warranted",
            LiquidityRegime.TIGHT: "Liquidity tight - risk assets under pressure",
            LiquidityRegime.CRISIS: "Liquidity crisis - extreme risk-off environment",
        }
        base = desc_map.get(regime, "Unknown liquidity regime")
        return f"{base} (score={score:.0f}, trend={trend})"

    def clear(self) -> None:
        """Reset predictor state."""
        self.score_history.clear()
        self.regime_history.clear()
