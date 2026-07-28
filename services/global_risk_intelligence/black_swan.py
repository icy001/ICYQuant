"""Black Swan Detector.

Continuously scans for tail-risk events across geopolitical,
financial, regulatory, technological, and natural domains.
Quantifies probability and expected impact of extreme events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EventCategory(str, Enum):
    """Black swan event categories."""

    GEOPOLITICAL = "geopolitical"
    FINANCIAL = "financial"
    REGULATORY = "regulatory"
    TECHNOLOGICAL = "technological"
    NATURAL = "natural"


class EventSeverity(str, Enum):
    """Event severity classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class BlackSwanSignal:
    """A detected black-swan precursor signal.

    Attributes:
        category: Event category.
        signal_name: Short identifier.
        probability: Estimated probability [0.0, 1.0].
        impact: Estimated portfolio impact (fraction).
        severity: Event severity classification.
        description: Human-readable description.
        indicators: Supporting indicators.
    """

    category: EventCategory = EventCategory.GEOPOLITICAL
    signal_name: str = ""
    probability: float = 0.01
    impact: float = 0.0  # Expected portfolio impact as fraction
    severity: EventSeverity = EventSeverity.LOW
    description: str = ""
    indicators: dict[str, float] = field(default_factory=dict)

    @property
    def expected_loss(self) -> float:
        """Expected loss = probability × impact."""
        return self.probability * self.impact

    @property
    def is_urgent(self) -> bool:
        return self.probability >= 0.20 or self.impact >= 0.15


@dataclass
class BlackSwanAssessment:
    """Complete black swan risk assessment.

    Attributes:
        overall_probability: Aggregated black swan probability.
        overall_impact: Aggregate expected portfolio impact.
        signals: Active black swan signals.
        severity: Overall severity.
        description: Human-readable summary.
        recommended_hedge: Recommended hedging cost (% of portfolio).
        timestamp: Assessment timestamp.
    """

    overall_probability: float = 0.01
    overall_impact: float = 0.0
    signals: list[BlackSwanSignal] = field(default_factory=list)
    severity: EventSeverity = EventSeverity.LOW
    description: str = ""
    recommended_hedge: float = 0.0  # % of portfolio for tail hedges
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_defcon(self) -> bool:
        """Whether tail hedge is warranted."""
        return self.severity in (EventSeverity.HIGH, EventSeverity.EXTREME)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class BlackSwanDetector:
    """Detects tail-risk / black swan precursor signals.

    Scans five categories using configurable signal detectors:
      - Geopolitical: war risk, sanctions, trade disruption
      - Financial: credit event, bank failure, currency crisis
      - Regulatory: policy shock, capital controls, market closure
      - Technological: cyber attack, exchange outage, model failure
      - Natural: pandemic, natural disaster, climate event

    Attributes:
        category_weights: Contribution weights per category.
        signal_threshold: Minimum signal probability to report.
    """

    CATEGORY_WEIGHTS: dict[str, float] = {
        "geopolitical": 0.25,
        "financial": 0.30,
        "regulatory": 0.15,
        "technological": 0.15,
        "natural": 0.15,
    }

    # Predefined signal detectors per category
    SIGNAL_LIBRARY: dict[EventCategory, list[dict[str, Any]]] = {
        EventCategory.GEOPOLITICAL: [
            {"name": "war_risk", "base_prob": 0.005, "impact": 0.25,
             "severity": EventSeverity.EXTREME,
             "desc": "Military conflict in major economy region"},
            {"name": "sanctions", "base_prob": 0.01, "impact": 0.12,
             "severity": EventSeverity.HIGH,
             "desc": "Major sanctions on key economy"},
            {"name": "trade_disruption", "base_prob": 0.02, "impact": 0.08,
             "severity": EventSeverity.MEDIUM,
             "desc": "Supply chain / trade route disruption"},
        ],
        EventCategory.FINANCIAL: [
            {"name": "credit_event", "base_prob": 0.01, "impact": 0.20,
             "severity": EventSeverity.EXTREME,
             "desc": "Major credit default or restructuring"},
            {"name": "bank_failure", "base_prob": 0.008, "impact": 0.25,
             "severity": EventSeverity.EXTREME,
             "desc": "Systemically important bank failure"},
            {"name": "currency_crisis", "base_prob": 0.015, "impact": 0.15,
             "severity": EventSeverity.HIGH,
             "desc": "Currency collapse in major economy"},
            {"name": "flash_crash", "base_prob": 0.02, "impact": 0.10,
             "severity": EventSeverity.HIGH,
             "desc": "Algorithmic flash crash"},
        ],
        EventCategory.REGULATORY: [
            {"name": "policy_shock", "base_prob": 0.02, "impact": 0.10,
             "severity": EventSeverity.MEDIUM,
             "desc": "Sudden monetary/fiscal policy change"},
            {"name": "capital_controls", "base_prob": 0.015, "impact": 0.12,
             "severity": EventSeverity.HIGH,
             "desc": "Capital controls imposed"},
            {"name": "market_closure", "base_prob": 0.005, "impact": 0.30,
             "severity": EventSeverity.EXTREME,
             "desc": "Exchange/market closure"},
        ],
        EventCategory.TECHNOLOGICAL: [
            {"name": "cyber_attack", "base_prob": 0.02, "impact": 0.08,
             "severity": EventSeverity.MEDIUM,
             "desc": "Major cyber attack on financial infrastructure"},
            {"name": "exchange_outage", "base_prob": 0.015, "impact": 0.06,
             "severity": EventSeverity.MEDIUM,
             "desc": "Extended exchange system outage"},
            {"name": "model_failure", "base_prob": 0.01, "impact": 0.10,
             "severity": EventSeverity.HIGH,
             "desc": "Systemic quant model failure"},
        ],
        EventCategory.NATURAL: [
            {"name": "pandemic", "base_prob": 0.005, "impact": 0.30,
             "severity": EventSeverity.EXTREME,
             "desc": "Global pandemic outbreak"},
            {"name": "natural_disaster", "base_prob": 0.015, "impact": 0.06,
             "severity": EventSeverity.MEDIUM,
             "desc": "Major natural disaster in financial center"},
            {"name": "climate_event", "base_prob": 0.01, "impact": 0.08,
             "severity": EventSeverity.MEDIUM,
             "desc": "Extreme climate event disrupting markets"},
        ],
    }

    def __init__(self, signal_threshold: float = 0.005) -> None:
        self.signal_threshold = signal_threshold
        self._market_stress_multiplier: float = 1.0

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def detect(self,
               market_stress: float = 0.1,
               vix: float = 15.0,
               credit_spread: float = 1.0,
               geopolitical_tension: float = 0.0,
               cyber_threat_level: float = 0.0,
               ) -> BlackSwanAssessment:
        """Scan for black swan precursor signals.

        Args:
            market_stress: Current market stress level [0, 1].
            vix: VIX level.
            credit_spread: Credit spread.
            geopolitical_tension: Geopolitical tension indicator.
            cyber_threat_level: Cyber threat indicator.

        Returns:
            BlackSwanAssessment with active signals.
        """
        # Market stress amplifies all black swan probabilities
        self._market_stress_multiplier = 1.0 + market_stress * 2.0

        signals: list[BlackSwanSignal] = []

        for category, signal_defs in self.SIGNAL_LIBRARY.items():
            # Category-specific modifiers
            cat_modifier = self._category_modifier(
                category, vix, credit_spread,
                geopolitical_tension, cyber_threat_level,
            )

            for sd in signal_defs:
                prob = sd["base_prob"] * self._market_stress_multiplier * cat_modifier
                prob = min(0.50, prob)  # Cap at 50%

                if prob >= self.signal_threshold:
                    signals.append(BlackSwanSignal(
                        category=category,
                        signal_name=sd["name"],
                        probability=round(prob, 4),
                        impact=sd["impact"],
                        severity=sd["severity"],
                        description=sd["desc"],
                        indicators={
                            "base_prob": sd["base_prob"],
                            "market_multiplier": self._market_stress_multiplier,
                            "cat_modifier": cat_modifier,
                        },
                    ))

        # Sort by expected loss (descending)
        signals.sort(key=lambda s: s.expected_loss, reverse=True)

        # Aggregate probability (union probability approximation)
        if signals:
            union_prob = 1.0
            for s in signals:
                union_prob *= (1.0 - s.probability)
            overall_prob = round(1.0 - union_prob, 4)
        else:
            overall_prob = 0.0

        # Aggregate impact (worst-case among active)
        overall_impact = max((s.impact for s in signals), default=0.0)

        # Severity
        severity = self._classify_severity(overall_prob, overall_impact, signals)

        # Hedge recommendation: spend % of portfolio on tail hedges
        hedge = self._recommend_hedge(overall_prob, overall_impact, severity)

        description = self._describe(severity, overall_prob, signals)

        return BlackSwanAssessment(
            overall_probability=overall_prob,
            overall_impact=overall_impact,
            signals=signals,
            severity=severity,
            description=description,
            recommended_hedge=hedge,
        )

    # ------------------------------------------------------------------
    # Category modifiers
    # ------------------------------------------------------------------

    def _category_modifier(self, category: EventCategory,
                           vix: float, credit_spread: float,
                           geopolitical_tension: float,
                           cyber_threat_level: float) -> float:
        """Adjust signal probabilities based on current conditions."""
        modifier = 1.0

        if category == EventCategory.FINANCIAL:
            if vix > 25:
                modifier *= 1.5
            if credit_spread > 2.0:
                modifier *= 1.4
            if vix > 35:
                modifier *= 1.5

        elif category == EventCategory.GEOPOLITICAL:
            if geopolitical_tension > 0.5:
                modifier *= 2.0
            elif geopolitical_tension > 0.25:
                modifier *= 1.5

        elif category == EventCategory.TECHNOLOGICAL:
            if cyber_threat_level > 0.5:
                modifier *= 2.0
            elif cyber_threat_level > 0.25:
                modifier *= 1.5

        elif category == EventCategory.NATURAL:
            pass  # Natural events don't correlate with market conditions

        elif category == EventCategory.REGULATORY:
            if vix > 30:
                modifier *= 1.3

        return modifier

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def _classify_severity(self, prob: float, impact: float,
                           signals: list[BlackSwanSignal]) -> EventSeverity:
        extreme_count = sum(1 for s in signals
                            if s.severity == EventSeverity.EXTREME and s.probability > 0.01)
        high_count = sum(1 for s in signals
                         if s.severity in (EventSeverity.HIGH, EventSeverity.EXTREME)
                         and s.probability > 0.01)

        if prob >= 0.15 or extreme_count >= 3:
            return EventSeverity.EXTREME
        elif prob >= 0.08 or high_count >= 3:
            return EventSeverity.HIGH
        elif prob >= 0.03 or high_count >= 1:
            return EventSeverity.MEDIUM
        return EventSeverity.LOW

    def _recommend_hedge(self, prob: float, impact: float,
                         severity: EventSeverity) -> float:
        """Recommend tail hedge budget as % of portfolio."""
        if severity == EventSeverity.EXTREME:
            return min(0.05, impact * 0.6)
        elif severity == EventSeverity.HIGH:
            return min(0.03, impact * 0.4)
        elif severity == EventSeverity.MEDIUM:
            return min(0.01, impact * 0.2)
        return 0.0

    def _describe(self, severity: EventSeverity, prob: float,
                  signals: list[BlackSwanSignal]) -> str:
        level = severity.value.upper()
        top = [f"{s.signal_name}(p={s.probability:.3f})" for s in signals[:3]]
        return (f"[{level}] Black swan probability: {prob:.1%}. "
                f"Top signals: {', '.join(top) if top else 'none'}")

    # ------------------------------------------------------------------
    # Quick scan
    # ------------------------------------------------------------------

    def quick_scan(self, market_stress: float = 0.1,
                   vix: float = 15.0) -> dict[str, Any]:
        """Fast black swan scan."""
        assessment = self.detect(market_stress=market_stress, vix=vix)
        return {
            "probability": assessment.overall_probability,
            "severity": assessment.severity.value,
            "is_defcon": assessment.is_defcon,
            "hedge_recommendation": assessment.recommended_hedge,
            "signal_count": len(assessment.signals),
        }
