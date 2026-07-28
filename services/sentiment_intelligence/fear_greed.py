"""AI Fear & Greed Model.

Constructs a multi-dimensional Fear & Greed Index by aggregating signals
from volatility, put/call ratio, momentum, fund flows, and social sentiment.
Outputs a 0-100 score with zone classification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .record import FearGreedZone


@dataclass
class FearGreedResult:
    """Result of Fear & Greed index calculation.

    Attributes:
        score: Fear & Greed score [0, 100] (0=extreme fear, 100=extreme greed).
        zone: Classified Fear & Greed zone.
        components: Individual component scores and weights.
        timestamp: Calculation timestamp.
        previous_score: Previous index score for momentum analysis.
        change: Change from previous score.
        description: Human-readable interpretation.
        signals: Raw input signals used for calculation.
    """

    score: float = 50.0
    zone: FearGreedZone = FearGreedZone.NEUTRAL
    components: dict[str, dict[str, Any]] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    previous_score: float | None = None
    change: float = 0.0
    description: str = ""
    signals: dict[str, float] = field(default_factory=dict)

    @property
    def is_extreme_fear(self) -> bool:
        return self.zone == FearGreedZone.EXTREME_FEAR

    @property
    def is_extreme_greed(self) -> bool:
        return self.zone == FearGreedZone.EXTREME_GREED

    @property
    def is_extreme(self) -> bool:
        return self.zone in (FearGreedZone.EXTREME_FEAR, FearGreedZone.EXTREME_GREED)

    @property
    def momentum(self) -> float:
        return self.change

    @property
    def is_rising(self) -> bool:
        return self.change > 0

    @property
    def is_falling(self) -> bool:
        return self.change < 0


class FearGreedModel:
    """Multi-dimensional AI Fear & Greed Index.

    Aggregates five core components into a single 0-100 index:
    - Market Volatility (25%): VIX-like volatility measure
    - Put/Call Ratio (20%): Options market sentiment
    - Price Momentum (20%): Market breadth and momentum
    - Fund Flow (20%): Capital flow direction
    - Social Sentiment (15%): Crowd sentiment from social media
    """

    def __init__(self) -> None:
        self.weights: dict[str, float] = {
            "volatility": 0.25,
            "put_call_ratio": 0.20,
            "price_momentum": 0.20,
            "fund_flow": 0.20,
            "social_sentiment": 0.15,
        }
        self.score_history: list[float] = []
        self.component_history: dict[str, list[float]] = {
            comp: [] for comp in self.weights
        }
        self.threshold_extreme_greed: float = 75.0
        self.threshold_greed: float = 60.0
        self.threshold_fear: float = 40.0
        self.threshold_extreme_fear: float = 25.0

    # --- Calculation ---

    def calculate(self, data: dict[str, float] | None = None) -> float:
        """Calculate the Fear & Greed index score."""
        if data is None:
            return 50.0
        weighted_sum = 0.0
        total_weight = 0.0
        for component, weight in self.weights.items():
            if component in data:
                value = max(0.0, min(100.0, data[component]))
                weighted_sum += value * weight
                total_weight += weight
        if total_weight == 0:
            return 50.0
        score = weighted_sum / total_weight
        self.score_history.append(score)
        if len(self.score_history) > 200:
            self.score_history = self.score_history[-200:]
        return score

    def analyze(self, data: dict[str, float] | None = None) -> FearGreedResult:
        """Full Fear & Greed analysis with zone classification and momentum."""
        score = self.calculate(data)
        zone = self._score_to_zone(score)
        previous_score = (
            self.score_history[-2] if len(self.score_history) >= 2 else None
        )
        change = score - previous_score if previous_score is not None else 0.0
        components: dict[str, dict[str, Any]] = {}
        if data:
            for name in self.weights:
                if name in data:
                    value = data[name]
                    components[name] = {
                        "value": value,
                        "weight": self.weights[name],
                        "contribution": value * self.weights[name],
                        "normalized": self._normalize_component(name, value),
                    }
                    self.component_history[name].append(value)
        description = self._generate_description(score, zone, change)
        return FearGreedResult(
            score=score,
            zone=zone,
            components=components,
            previous_score=previous_score,
            change=change,
            description=description,
            signals=data or {},
        )

    def analyze_from_components(
        self,
        volatility: float | None = None,
        put_call_ratio: float | None = None,
        price_momentum: float | None = None,
        fund_flow: float | None = None,
        social_sentiment: float | None = None,
    ) -> FearGreedResult:
        """Calculate index from individual component values."""
        data: dict[str, float] = {}
        if volatility is not None:
            data["volatility"] = max(0.0, min(100.0, volatility))
        if put_call_ratio is not None:
            data["put_call_ratio"] = max(0.0, min(100.0, put_call_ratio))
        if price_momentum is not None:
            data["price_momentum"] = max(0.0, min(100.0, price_momentum))
        if fund_flow is not None:
            data["fund_flow"] = max(0.0, min(100.0, fund_flow))
        if social_sentiment is not None:
            data["social_sentiment"] = max(0.0, min(100.0, social_sentiment))
        return self.analyze(data)

    # --- Zone ---

    def _score_to_zone(self, score: float) -> FearGreedZone:
        if score >= self.threshold_extreme_greed:
            return FearGreedZone.EXTREME_GREED
        elif score >= self.threshold_greed:
            return FearGreedZone.GREED
        elif score > self.threshold_fear:
            return FearGreedZone.NEUTRAL
        elif score > self.threshold_extreme_fear:
            return FearGreedZone.FEAR
        else:
            return FearGreedZone.EXTREME_FEAR

    # --- Analysis Helpers ---

    def get_trend(self, window: int = 10) -> str:
        """Get the trend of the Fear & Greed index."""
        if len(self.score_history) < 2:
            return "stable"
        recent = self.score_history[-window:]
        if len(recent) < 2:
            return "stable"
        mid = len(recent) // 2
        first_half = sum(recent[:mid]) / mid
        second_half = sum(recent[mid:]) / (len(recent) - mid)
        diff = second_half - first_half
        if diff > 5:
            return "rising"
        elif diff < -5:
            return "falling"
        return "stable"

    def get_contrarian_signal(self) -> str:
        """Get contrarian trading signal based on extreme zones."""
        if not self.score_history:
            return "neutral"
        current = self.score_history[-1]
        zone = self._score_to_zone(current)
        if zone == FearGreedZone.EXTREME_FEAR:
            return "buy"
        elif zone == FearGreedZone.EXTREME_GREED:
            return "sell"
        elif zone == FearGreedZone.FEAR:
            return "consider_buy"
        elif zone == FearGreedZone.GREED:
            return "consider_sell"
        return "neutral"

    def get_risk_adjustment(self) -> float:
        """Get position size adjustment factor based on Fear & Greed."""
        if not self.score_history:
            return 1.0
        current = self.score_history[-1]
        zone = self._score_to_zone(current)
        if zone == FearGreedZone.EXTREME_FEAR:
            return 0.5
        elif zone == FearGreedZone.EXTREME_GREED:
            return 0.6
        elif zone == FearGreedZone.FEAR:
            return 1.2
        elif zone == FearGreedZone.GREED:
            return 0.8
        return 1.0

    def set_weights(self, weights: dict[str, float]) -> None:
        """Update component weights (auto-normalized)."""
        total = sum(weights.values())
        self.weights = {k: v / total for k, v in weights.items()}

    # --- Internal ---

    def _normalize_component(self, name: str, value: float) -> str:
        """Normalize a component value to a human-readable level."""
        if value >= 75:
            if name in ("volatility", "put_call_ratio"):
                return "extreme_fear"
            return "extreme_greed"
        elif value >= 60:
            if name in ("volatility", "put_call_ratio"):
                return "fear"
            return "greed"
        elif value >= 40:
            return "neutral"
        elif value >= 25:
            if name in ("volatility", "put_call_ratio"):
                return "greed"
            return "fear"
        else:
            if name in ("volatility", "put_call_ratio"):
                return "extreme_greed"
            return "extreme_fear"

    def _generate_description(
        self, score: float, zone: FearGreedZone, change: float
    ) -> str:
        """Generate a human-readable interpretation."""
        zone_descriptions = {
            FearGreedZone.EXTREME_GREED: "Market is extremely greedy - high risk of correction",
            FearGreedZone.GREED: "Market is greedy - bullish sentiment dominates",
            FearGreedZone.NEUTRAL: "Market sentiment is balanced",
            FearGreedZone.FEAR: "Market is fearful - bearish pressure increasing",
            FearGreedZone.EXTREME_FEAR: "Market is extremely fearful - potential buying opportunity",
        }
        desc = zone_descriptions.get(zone, "Unknown zone")
        if abs(change) >= 10:
            direction = "rapidly increasing" if change > 0 else "rapidly decreasing"
            desc += f" (sentiment {direction})"
        return desc

    def clear(self) -> None:
        """Reset model state."""
        self.score_history.clear()
        for comp in self.component_history:
            self.component_history[comp].clear()
