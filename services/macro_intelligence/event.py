"""Macro Event Impact Predictor.

Predicts the potential market impact of scheduled and unscheduled
macro events using historical pattern analysis and multi-asset
sensitivity modeling.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from .data import MacroEvent, MacroDataSnapshot


class ImpactDirection(str, Enum):
    """Direction of predicted impact."""
    STRONG_POSITIVE = "strong_positive"
    POSITIVE = "positive"
    SLIGHTLY_POSITIVE = "slightly_positive"
    NEUTRAL = "neutral"
    SLIGHTLY_NEGATIVE = "slightly_negative"
    NEGATIVE = "negative"
    STRONG_NEGATIVE = "strong_negative"


class ImpactMagnitude(str, Enum):
    """Magnitude of predicted impact."""
    EXTREME = "extreme"       # >3 sigma moves expected
    HIGH = "high"             # 2-3 sigma
    MODERATE = "moderate"     # 1-2 sigma
    LOW = "low"               # 0.5-1 sigma
    MINIMAL = "minimal"       # <0.5 sigma


class EventCategory(str, Enum):
    """Category of macro event."""
    CENTRAL_BANK = "central_bank"         # FOMC, ECB, etc.
    INFLATION = "inflation"               # CPI, PPI, PCE
    EMPLOYMENT = "employment"             # NFP, unemployment
    GROWTH = "growth"                     # GDP, PMI
    GEOPOLITICAL = "geopolitical"         # conflicts, elections
    FINANCIAL_STABILITY = "financial_stability"  # bank stress, contagion
    COMMODITY = "commodity"               # OPEC, supply shocks
    UNKNOWN = "unknown"


@dataclass
class AssetImpact:
    """Predicted impact on a specific asset class.

    Attributes:
        asset: Asset class name (e.g. "US_Equities", "UST_10Y", "USD").
        direction: Predicted direction.
        magnitude: Predicted magnitude.
        probability: Probability of this outcome (0-1).
        expected_move_pct: Expected percentage move.
        confidence_interval: (low, high) confidence interval for move.
        rationale: Explanation for the prediction.
    """
    asset: str
    direction: ImpactDirection
    magnitude: ImpactMagnitude
    probability: float = 0.5
    expected_move_pct: float = 0.0
    confidence_interval: tuple[float, float] = (0.0, 0.0)
    rationale: str = ""

    @property
    def is_positive(self) -> bool:
        return self.direction in (
            ImpactDirection.POSITIVE,
            ImpactDirection.STRONG_POSITIVE,
            ImpactDirection.SLIGHTLY_POSITIVE,
        )

    @property
    def is_negative(self) -> bool:
        return self.direction in (
            ImpactDirection.NEGATIVE,
            ImpactDirection.STRONG_NEGATIVE,
            ImpactDirection.SLIGHTLY_NEGATIVE,
        )

    @property
    def summary(self) -> str:
        return f"{self.asset}: {self.direction.value} ({self.magnitude.value}, prob={self.probability:.0%})"


@dataclass
class EventImpactPrediction:
    """Complete event impact prediction.

    Attributes:
        event: The macro event being analyzed.
        category: Classified event category.
        overall_direction: Aggregate impact direction.
        overall_magnitude: Aggregate impact magnitude.
        confidence: Overall prediction confidence (0-1).
        asset_impacts: Per-asset impact predictions.
        pre_event_bias: Market bias before the event.
        surprise_scenarios: Alternative scenarios with probabilities.
        risk_warnings: Any risk warnings for this event.
        details: Additional prediction details.
        timestamp: Prediction timestamp.
    """
    event: MacroEvent
    category: EventCategory
    overall_direction: ImpactDirection
    overall_magnitude: ImpactMagnitude
    confidence: float = 0.5
    asset_impacts: list[AssetImpact] = field(default_factory=list)
    pre_event_bias: str = "neutral"
    surprise_scenarios: list[dict[str, Any]] = field(default_factory=list)
    risk_warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_high_impact(self) -> bool:
        return self.overall_magnitude in (
            ImpactMagnitude.HIGH,
            ImpactMagnitude.EXTREME,
        )

    @property
    def summary(self) -> str:
        return (
            f"[{self.event.name}] {self.category.value}: "
            f"{self.overall_direction.value} "
            f"({self.overall_magnitude.value}, confidence: {self.confidence:.0%})"
        )


class EventImpactPredictor:
    """Predicts market impact of macro events.

    Uses event categorization, historical pattern matching, and
    current macro context to predict how markets will react to
    upcoming economic events and data releases.
    """

    # Event category keywords for classification
    _CATEGORY_KEYWORDS: dict[EventCategory, list[str]] = {
        EventCategory.CENTRAL_BANK: [
            "fomc", "fed", "ecb", "boj", "boe", "rate decision",
            "monetary policy", "central bank",
        ],
        EventCategory.INFLATION: [
            "cpi", "ppi", "pce", "inflation", "price index",
        ],
        EventCategory.EMPLOYMENT: [
            "nfp", "nonfarm", "payroll", "employment", "unemployment",
            "jobless claims", "wage",
        ],
        EventCategory.GROWTH: [
            "gdp", "pmi", "ism", "retail sales", "industrial production",
            "durable goods", "factory orders",
        ],
        EventCategory.GEOPOLITICAL: [
            "election", "war", "conflict", "sanction", "geopolitical",
            "tariff", "trade war",
        ],
        EventCategory.FINANCIAL_STABILITY: [
            "bank", "credit event", "default", "contagion",
            "systemic risk", "bailout",
        ],
        EventCategory.COMMODITY: [
            "opec", "oil", "commodity", "supply", "energy",
            "gold", "copper",
        ],
    }

    # Default asset sensitivity to event categories
    _ASSET_SENSITIVITY: dict[EventCategory, dict[str, float]] = {
        EventCategory.CENTRAL_BANK: {
            "US_Equities": 0.8, "UST_10Y": 1.0, "USD": 1.0,
            "Gold": 0.6, "EM_Equities": 0.5,
        },
        EventCategory.INFLATION: {
            "US_Equities": 0.7, "UST_10Y": 0.9, "USD": 0.6,
            "Gold": 0.8, "Commodities": 0.5,
        },
        EventCategory.EMPLOYMENT: {
            "US_Equities": 0.8, "UST_10Y": 0.7, "USD": 0.8,
            "Gold": 0.4,
        },
        EventCategory.GROWTH: {
            "US_Equities": 0.9, "UST_10Y": 0.5, "USD": 0.4,
            "EM_Equities": 0.7, "Commodities": 0.6,
        },
        EventCategory.GEOPOLITICAL: {
            "US_Equities": 0.5, "Gold": 1.0, "Oil": 1.0,
            "USD": 0.4, "EM_Equities": 0.8,
        },
        EventCategory.FINANCIAL_STABILITY: {
            "US_Equities": 0.9, "UST_10Y": 0.7, "Credit": 1.0,
            "USD": 0.5, "Gold": 0.6,
        },
        EventCategory.COMMODITY: {
            "Oil": 1.0, "Commodities": 0.9, "EM_Equities": 0.5,
            "USD": 0.4,
        },
    }

    def __init__(self):
        self._predictions: list[EventImpactPrediction] = []

    def predict(self, event: MacroEvent,
                macro_context: Optional[MacroDataSnapshot] = None) -> EventImpactPrediction:
        """Predict the market impact of a macro event.

        Args:
            event: The macro event to analyze.
            macro_context: Optional current macro context for conditioning.

        Returns:
            EventImpactPrediction with per-asset impact estimates.
        """
        # 1. Classify event category
        category = self._classify_event(event)

        # 2. Determine overall direction from event characteristics
        direction = self._determine_direction(event, category, macro_context)

        # 3. Determine magnitude from importance and volatility context
        magnitude = self._determine_magnitude(event, category, macro_context)

        # 4. Generate per-asset impacts
        asset_impacts = self._generate_asset_impacts(
            event, category, direction, magnitude, macro_context,
        )

        # 5. Compute confidence
        confidence = self._compute_confidence(event, category, macro_context)

        # 6. Risk warnings
        warnings = self._generate_warnings(event, category)

        prediction = EventImpactPrediction(
            event=event,
            category=category,
            overall_direction=direction,
            overall_magnitude=magnitude,
            confidence=confidence,
            asset_impacts=asset_impacts,
            risk_warnings=warnings,
            details={
                "importance": event.importance,
                "country": event.country,
                "historical_impact": event.historical_impact,
            },
        )

        self._predictions.append(prediction)
        return prediction

    def predict_from_dict(self, data: dict[str, Any]) -> EventImpactPrediction:
        """Predict from a simple data dict.

        Convenience method for testing.

        Args:
            data: Dict with keys: name, event_type, importance, country,
                  assets_affected, historical_impact.

        Returns:
            EventImpactPrediction result.
        """
        event = MacroEvent(
            name=data.get("name", "Unknown Event"),
            event_type=data.get("event_type", "data_release"),
            country=data.get("country", "US"),
            importance=data.get("importance", 3),
            assets_affected=data.get("assets_affected", []),
            historical_impact=data.get("historical_impact", {}),
        )
        return self.predict(event)

    def get_history(self) -> list[EventImpactPrediction]:
        """Get historical predictions."""
        return list(self._predictions)

    # ── Private helpers ─────────────────────────────────────────────

    def _classify_event(self, event: MacroEvent) -> EventCategory:
        """Classify event into a category based on name and type."""
        name_lower = event.name.lower()
        type_lower = event.event_type.lower()

        for category, keywords in self._CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw in name_lower or kw in type_lower:
                    return category

        return EventCategory.UNKNOWN

    def _determine_direction(self, event: MacroEvent, category: EventCategory,
                             macro_context: Optional[MacroDataSnapshot]) -> ImpactDirection:
        """Determine the expected market impact direction."""
        # Use historical impact if available
        if event.historical_impact:
            avg_impact = sum(event.historical_impact.values()) / len(event.historical_impact)
            if avg_impact > 0.3:
                return ImpactDirection.POSITIVE
            elif avg_impact < -0.3:
                return ImpactDirection.NEGATIVE

        # Default: high importance events tend to create uncertainty
        if event.importance >= 4:
            return ImpactDirection.SLIGHTLY_NEGATIVE

        return ImpactDirection.NEUTRAL

    def _determine_magnitude(self, event: MacroEvent, category: EventCategory,
                             macro_context: Optional[MacroDataSnapshot]) -> ImpactMagnitude:
        """Determine the expected magnitude of impact."""
        if event.importance == 5:
            return ImpactMagnitude.EXTREME
        elif event.importance == 4:
            return ImpactMagnitude.HIGH
        elif event.importance == 3:
            return ImpactMagnitude.MODERATE
        elif event.importance == 2:
            return ImpactMagnitude.LOW
        else:
            return ImpactMagnitude.MINIMAL

    def _generate_asset_impacts(self, event: MacroEvent, category: EventCategory,
                                direction: ImpactDirection, magnitude: ImpactMagnitude,
                                macro_context: Optional[MacroDataSnapshot]) -> list[AssetImpact]:
        """Generate per-asset impact predictions."""
        sensitivity = self._ASSET_SENSITIVITY.get(category, {})
        impacts: list[AssetImpact] = []

        for asset, sensitivity_weight in sensitivity.items():
            # Scale expected move by sensitivity and magnitude
            magnitude_factor = {
                ImpactMagnitude.EXTREME: 3.0,
                ImpactMagnitude.HIGH: 2.0,
                ImpactMagnitude.MODERATE: 1.0,
                ImpactMagnitude.LOW: 0.5,
                ImpactMagnitude.MINIMAL: 0.1,
            }[magnitude]

            direction_sign = 1.0 if "positive" in direction.value else (
                -1.0 if "negative" in direction.value else 0.0
            )

            expected_move = direction_sign * magnitude_factor * sensitivity_weight

            impacts.append(AssetImpact(
                asset=asset,
                direction=direction,
                magnitude=magnitude,
                probability=0.6,
                expected_move_pct=round(expected_move, 2),
                confidence_interval=(
                    round(expected_move * 0.5, 2),
                    round(expected_move * 1.5, 2),
                ),
                rationale=f"Sensitivity: {sensitivity_weight:.1f}, magnitude: {magnitude_factor:.1f}",
            ))

        return impacts

    def _compute_confidence(self, event: MacroEvent, category: EventCategory,
                            macro_context: Optional[MacroDataSnapshot]) -> float:
        """Compute prediction confidence."""
        base_confidence = 0.5

        # Higher confidence for well-understood events
        if category in (EventCategory.EMPLOYMENT, EventCategory.INFLATION):
            base_confidence += 0.1

        # Lower confidence for geopolitical
        if category == EventCategory.GEOPOLITICAL:
            base_confidence -= 0.15

        # Lower confidence for unknown
        if category == EventCategory.UNKNOWN:
            base_confidence -= 0.2

        # Historical data boosts confidence
        if event.historical_impact:
            base_confidence += 0.1

        return min(0.9, max(0.2, base_confidence))

    def _generate_warnings(self, event: MacroEvent,
                           category: EventCategory) -> list[str]:
        """Generate risk warnings for the event."""
        warnings: list[str] = []

        if event.importance >= 4:
            warnings.append("High importance event — expect elevated volatility")

        if category == EventCategory.CENTRAL_BANK:
            warnings.append("Central bank events carry tail risk of surprise")

        if category == EventCategory.GEOPOLITICAL:
            warnings.append("Geopolitical events are inherently unpredictable")

        if category == EventCategory.UNKNOWN:
            warnings.append("Unclassified event — limited historical analogs")

        return warnings


__all__ = [
    "ImpactDirection",
    "ImpactMagnitude",
    "EventCategory",
    "AssetImpact",
    "EventImpactPrediction",
    "EventImpactPredictor",
]
