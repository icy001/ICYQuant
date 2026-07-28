"""Economic Cycle Detector.

Detects the current phase of the economic cycle based on a composite
analysis of growth, employment, production, and leading indicators.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from .data import IndicatorCategory, MacroDataSnapshot, MacroIndicator


class CyclePhase(str, Enum):
    """Phases of the economic cycle."""
    DEEP_RECESSION = "deep_recession"
    RECESSION = "recession"
    EARLY_RECOVERY = "early_recovery"
    RECOVERY = "recovery"
    EARLY_EXPANSION = "early_expansion"
    EXPANSION = "expansion"
    LATE_CYCLE = "late_cycle"
    PEAK = "peak"
    CONTRACTION = "contraction"
    UNKNOWN = "unknown"


@dataclass
class CycleResult:
    """Economic cycle detection result.

    Attributes:
        phase: Detected cycle phase.
        confidence: Classification confidence (0-1).
        growth_momentum: Growth momentum score (-1 to 1).
        employment_momentum: Employment momentum score (-1 to 1).
        leading_indicator_momentum: Leading indicators momentum.
        details: Per-component breakdown.
        timestamp: Detection timestamp.
    """
    phase: CyclePhase
    confidence: float
    growth_momentum: float = 0.0
    employment_momentum: float = 0.0
    leading_indicator_momentum: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_expansionary(self) -> bool:
        return self.phase in (
            CyclePhase.EARLY_EXPANSION,
            CyclePhase.EXPANSION,
        )

    @property
    def is_contractionary(self) -> bool:
        return self.phase in (
            CyclePhase.RECESSION,
            CyclePhase.DEEP_RECESSION,
            CyclePhase.CONTRACTION,
        )

    @property
    def summary(self) -> str:
        return f"{self.phase.value} (confidence: {self.confidence:.0%})"


class EconomicCycleDetector:
    """Detects the current economic cycle phase.

    Uses a multi-factor scoring approach combining:
    - GDP growth trajectory
    - Employment indicators (NFP, unemployment, wage growth)
    - Industrial production
    - PMI (manufacturing & services)
    - Leading economic indicators
    - Consumer/business sentiment
    - Yield curve signals
    """

    # Indicator weights for growth momentum
    _GROWTH_WEIGHTS: dict[str, float] = {
        "GDP": 0.25,
        "GDP_Growth": 0.20,
        "Industrial_Production": 0.15,
        "PMI_Manufacturing": 0.20,
        "PMI_Services": 0.10,
        "Retail_Sales": 0.10,
    }

    # Indicator weights for employment momentum
    _EMPLOYMENT_WEIGHTS: dict[str, float] = {
        "NFP": 0.30,
        "Unemployment_Rate": 0.25,
        "Wage_Growth": 0.20,
        "Jobless_Claims": 0.15,
        "Labor_Force_Participation": 0.10,
    }

    # Leading indicator weights
    _LEADING_WEIGHTS: dict[str, float] = {
        "LEI": 0.25,
        "Yield_Curve": 0.25,
        "Consumer_Confidence": 0.15,
        "Business_Confidence": 0.10,
        "New_Orders": 0.15,
        "Building_Permits": 0.10,
    }

    # Thresholds for GDP growth-based classification (YoY %)
    _GDP_DEEP_RECESSION = -3.0
    _GDP_RECESSION = 0.0
    _GDP_RECOVERY = 2.0
    _GDP_EXPANSION = 4.0

    def __init__(self):
        self._history: list[CycleResult] = []

    def detect(self, snapshot: MacroDataSnapshot) -> CycleResult:
        """Detect the economic cycle phase from a macro data snapshot.

        Args:
            snapshot: Current macro data snapshot.

        Returns:
            CycleResult with the detected phase and confidence.
        """
        # 1. Compute component momentum scores
        growth_momentum = self._compute_growth_momentum(snapshot)
        employment_momentum = self._compute_employment_momentum(snapshot)
        leading_momentum = self._compute_leading_momentum(snapshot)

        # 2. Get GDP-specific signal
        gdp = snapshot.get("GDP_Growth") or snapshot.get("GDP")
        gdp_value = gdp.value if gdp else None

        # 3. Determine cycle phase
        phase, confidence = self._classify_phase(
            growth_momentum, employment_momentum,
            leading_momentum, gdp_value,
        )

        result = CycleResult(
            phase=phase,
            confidence=confidence,
            growth_momentum=growth_momentum,
            employment_momentum=employment_momentum,
            leading_indicator_momentum=leading_momentum,
            details={
                "gdp_value": gdp_value,
                "components": {
                    "growth": growth_momentum,
                    "employment": employment_momentum,
                    "leading": leading_momentum,
                },
            },
        )
        self._history.append(result)
        return result

    def detect_from_dict(self, data: dict[str, float]) -> CycleResult:
        """Detect cycle from a simple data dict.

        Convenience method for testing and quick analysis.

        Args:
            data: Dict mapping indicator names to values.

        Returns:
            CycleResult with the detected phase.
        """
        snapshot = MacroDataSnapshot()
        for name, value in data.items():
            indicator = MacroIndicator(
                name=name,
                value=value,
                category=self._infer_category(name),
            )
            snapshot.add(indicator)
        return self.detect(snapshot)

    def get_history(self) -> list[CycleResult]:
        """Get historical cycle detections."""
        return list(self._history)

    # ── Private helpers ─────────────────────────────────────────────

    def _compute_growth_momentum(self, snapshot: MacroDataSnapshot) -> float:
        """Compute composite growth momentum score."""
        return self._weighted_score(snapshot, self._GROWTH_WEIGHTS)

    def _compute_employment_momentum(self, snapshot: MacroDataSnapshot) -> float:
        """Compute composite employment momentum score."""
        return self._weighted_score(snapshot, self._EMPLOYMENT_WEIGHTS)

    def _compute_leading_momentum(self, snapshot: MacroDataSnapshot) -> float:
        """Compute composite leading indicator momentum."""
        return self._weighted_score(snapshot, self._LEADING_WEIGHTS)

    def _weighted_score(self, snapshot: MacroDataSnapshot,
                        weights: dict[str, float]) -> float:
        """Compute weighted average score from available indicators."""
        total_weight = 0.0
        weighted_sum = 0.0

        for name, weight in weights.items():
            ind = snapshot.get(name)
            if ind is not None:
                signal = self._indicator_signal(ind)
                weighted_sum += signal * weight
                total_weight += weight

        if total_weight == 0:
            return 0.0
        return max(-1.0, min(1.0, weighted_sum / total_weight))

    @staticmethod
    def _indicator_signal(indicator: MacroIndicator) -> float:
        """Convert an indicator to a normalized signal (-1 to 1).

        Uses change from previous and surprise vs expectations.
        """
        signal = 0.0

        # Change from previous
        if indicator.change is not None:
            pct = indicator.change_pct
            if pct is not None:
                signal += min(1.0, max(-1.0, pct / 5.0)) * 0.6

        # Surprise vs expectations
        if indicator.surprise is not None:
            signal += min(1.0, max(-1.0, indicator.surprise * 0.5)) * 0.4

        # Apply directionality
        if indicator.direction.value == "negative":
            signal = -signal

        return min(1.0, max(-1.0, signal))

    def _classify_phase(self, growth: float, employment: float,
                        leading: float, gdp: Optional[float]) -> tuple[CyclePhase, float]:
        """Classify cycle phase from component scores."""
        composite = (growth * 0.40 + employment * 0.30 + leading * 0.30)

        # Use GDP as anchor if available
        if gdp is not None:
            if gdp <= self._GDP_DEEP_RECESSION:
                return CyclePhase.DEEP_RECESSION, 0.85
            elif gdp <= self._GDP_RECESSION:
                if leading > 0:
                    return CyclePhase.EARLY_RECOVERY, 0.65
                return CyclePhase.RECESSION, 0.75
            elif gdp <= self._GDP_RECOVERY:
                if composite > 0.3:
                    return CyclePhase.RECOVERY, 0.70
                return CyclePhase.EARLY_RECOVERY, 0.60
            elif gdp <= self._GDP_EXPANSION:
                if leading < -0.2:
                    return CyclePhase.LATE_CYCLE, 0.65
                return CyclePhase.EXPANSION, 0.70
            else:
                if leading < -0.3 and growth < 0.2:
                    return CyclePhase.PEAK, 0.60
                return CyclePhase.EXPANSION, 0.65

        # Fallback: classify from composite score alone
        if composite > 0.5:
            return CyclePhase.EXPANSION, 0.55
        elif composite > 0.2:
            return CyclePhase.EARLY_EXPANSION, 0.55
        elif composite > 0.0:
            return CyclePhase.RECOVERY, 0.50
        elif composite > -0.2:
            return CyclePhase.EARLY_RECOVERY, 0.45
        elif composite > -0.5:
            return CyclePhase.RECESSION, 0.50
        else:
            return CyclePhase.DEEP_RECESSION, 0.55

    @staticmethod
    def _infer_category(name: str) -> IndicatorCategory:
        """Infer indicator category from its name."""
        upper = name.upper()
        if any(k in upper for k in ("GDP", "PMI", "PRODUCTION", "RETAIL", "ORDERS")):
            return IndicatorCategory.GROWTH
        if any(k in upper for k in ("NFP", "EMPLOY", "UNEMPLOY", "WAGE", "JOBLESS")):
            return IndicatorCategory.EMPLOYMENT
        if any(k in upper for k in ("CPI", "PPI", "INFLATION", "PCE")):
            return IndicatorCategory.INFLATION
        if any(k in upper for k in ("CONSUMER_CONFIDENCE", "SENTIMENT", "BUSINESS_CONF")):
            return IndicatorCategory.SENTIMENT
        return IndicatorCategory.GROWTH


__all__ = ["CyclePhase", "CycleResult", "EconomicCycleDetector"]
