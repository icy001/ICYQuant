"""Inflation Intelligence Analyzer.

Analyzes inflation trends, expectations, and regime shifts
across multiple dimensions: headline, core, producer prices,
wages, commodities, and market-implied expectations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from .data import IndicatorCategory, MacroDataSnapshot, MacroIndicator


class InflationTrend(str, Enum):
    """Inflation trend direction."""
    RAPIDLY_RISING = "rapidly_rising"
    RISING = "rising"
    MODERATELY_RISING = "moderately_rising"
    STABLE = "stable"
    MODERATELY_COOLING = "moderately_cooling"
    COOLING = "cooling"
    RAPIDLY_COOLING = "rapidly_cooling"
    DEFLATIONARY = "deflationary"
    UNKNOWN = "unknown"


class InflationRegime(str, Enum):
    """Inflation regime classification."""
    DISINFLATION = "disinflation"         # inflation ↓ but still positive
    DEFLATION = "deflation"               # negative inflation
    STABLE_INFLATION = "stable_inflation"  # near target
    REACCELERATION = "reacceleration"     # inflation picking up again
    STAGFLATION = "stagflation"          # high inflation + weak growth
    HYPERINFLATION = "hyperinflation"     # extreme inflation (rare)


@dataclass
class InflationAnalysis:
    """Result of inflation analysis.

    Attributes:
        trend: Current inflation trend.
        regime: Inflation regime classification.
        headline_value: Latest headline CPI/PCE value.
        core_value: Latest core CPI/PCE value.
        momentum: Short-term inflation momentum (-1 to 1).
        expectations: Market-implied inflation expectations.
        confidence: Analysis confidence (0-1).
        target_deviation: Deviation from central bank target.
        leading_signals: Signals from leading indicators.
        details: Additional analysis details.
        timestamp: Analysis timestamp.
    """
    trend: InflationTrend
    regime: InflationRegime
    headline_value: float = 0.0
    core_value: float = 0.0
    momentum: float = 0.0
    expectations: float = 0.0
    confidence: float = 0.5
    target_deviation: Optional[float] = None
    leading_signals: dict[str, float] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_cooling(self) -> bool:
        return self.trend in (
            InflationTrend.COOLING,
            InflationTrend.RAPIDLY_COOLING,
            InflationTrend.MODERATELY_COOLING,
            InflationTrend.DEFLATIONARY,
        )

    @property
    def is_rising(self) -> bool:
        return self.trend in (
            InflationTrend.RISING,
            InflationTrend.RAPIDLY_RISING,
            InflationTrend.MODERATELY_RISING,
        )

    @property
    def is_problematic(self) -> bool:
        return self.regime in (
            InflationRegime.STAGFLATION,
            InflationRegime.HYPERINFLATION,
        )

    @property
    def summary(self) -> str:
        return f"{self.trend.value} (headline: {self.headline_value}%, confidence: {self.confidence:.0%})"


class InflationAnalyzer:
    """Analyzes inflation across multiple dimensions.

    Combines headline CPI/PCE, core inflation, producer prices,
    wage growth, commodity prices, and breakeven rates to
    determine the current inflation regime and trajectory.
    """

    # Central bank targets (default: 2%)
    _INFLATION_TARGETS: dict[str, float] = {
        "FED": 2.0,
        "ECB": 2.0,
        "BOE": 2.0,
        "BOJ": 2.0,
        "RBA": 2.5,
    }

    # Component weights for inflation momentum
    _COMPONENT_WEIGHTS: dict[str, float] = {
        "CPI": 0.25,
        "Core_CPI": 0.25,
        "PCE": 0.15,
        "Core_PCE": 0.15,
        "PPI": 0.10,
        "Wage_Growth": 0.05,
        "Commodity_Index": 0.05,
    }

    # Thresholds for trend classification (YoY %)
    _COOLING_THRESHOLD = -0.3       # MoM change to indicate cooling
    _RISING_THRESHOLD = 0.3          # MoM change to indicate rising
    _DEFLATION_THRESHOLD = 0.0       # Below this = deflation
    _LOW_INFLATION = 1.0             # Below target range
    _HIGH_INFLATION = 4.0            # Above comfortable range
    _EXTREME_INFLATION = 10.0        # Hyperinflation threshold

    def __init__(self, central_bank: str = "FED"):
        self.central_bank = central_bank
        self._history: list[InflationAnalysis] = []

    def analyze(self, snapshot: MacroDataSnapshot) -> InflationAnalysis:
        """Analyze inflation from a macro data snapshot.

        Args:
            snapshot: Current macro data snapshot with inflation indicators.

        Returns:
            InflationAnalysis with trend, regime, and details.
        """
        # 1. Extract headline and core values
        headline = self._get_headline(snapshot)
        core = self._get_core(snapshot)

        # 2. Compute momentum
        momentum = self._compute_momentum(snapshot)

        # 3. Get expectations
        expectations = self._get_expectations(snapshot)

        # 4. Classify trend
        trend = self._classify_trend(headline, core, momentum)

        # 5. Classify regime
        regime = self._classify_regime(headline, momentum)

        # 6. Target deviation
        target = self._INFLATION_TARGETS.get(self.central_bank, 2.0)
        deviation = headline - target if headline != 0 else None

        # 7. Leading signals
        leading = self._compute_leading_signals(snapshot)

        analysis = InflationAnalysis(
            trend=trend,
            regime=regime,
            headline_value=headline,
            core_value=core,
            momentum=momentum,
            expectations=expectations,
            confidence=self._compute_confidence(snapshot),
            target_deviation=deviation,
            leading_signals=leading,
            details={
                "central_bank": self.central_bank,
                "target": target,
                "components": self._extract_components(snapshot),
            },
        )

        self._history.append(analysis)
        return analysis

    def analyze_from_dict(self, data: dict[str, float]) -> InflationAnalysis:
        """Analyze from a simple data dict.

        Convenience method for testing.

        Args:
            data: Dict mapping indicator names to values.

        Returns:
            InflationAnalysis result.
        """
        snapshot = MacroDataSnapshot()
        for name, value in data.items():
            indicator = MacroIndicator(
                name=name,
                value=value,
                category=IndicatorCategory.INFLATION,
                direction=self._infer_direction(name),
            )
            snapshot.add(indicator)
        return self.analyze(snapshot)

    def get_history(self) -> list[InflationAnalysis]:
        """Get historical inflation analyses."""
        return list(self._history)

    # ── Private helpers ─────────────────────────────────────────────

    def _get_headline(self, snapshot: MacroDataSnapshot) -> float:
        """Get headline inflation value (CPI or PCE)."""
        for name in ("CPI", "PCE", "Headline_CPI"):
            ind = snapshot.get(name)
            if ind is not None:
                return ind.value
        return 0.0

    def _get_core(self, snapshot: MacroDataSnapshot) -> float:
        """Get core inflation value."""
        for name in ("Core_CPI", "Core_PCE"):
            ind = snapshot.get(name)
            if ind is not None:
                return ind.value
        return 0.0

    def _get_expectations(self, snapshot: MacroDataSnapshot) -> float:
        """Get market-implied inflation expectations."""
        for name in ("Breakeven_5Y", "Breakeven_10Y", "Inflation_Expectations"):
            ind = snapshot.get(name)
            if ind is not None:
                return ind.value
        return 2.0  # default to target

    def _compute_momentum(self, snapshot: MacroDataSnapshot) -> float:
        """Compute inflation momentum from changes."""
        total_weight = 0.0
        weighted_change = 0.0

        for name, weight in self._COMPONENT_WEIGHTS.items():
            ind = snapshot.get(name)
            if ind is not None and ind.change is not None:
                # Normalize: 0.5% MoM change = max signal
                signal = min(1.0, max(-1.0, ind.change / 0.5))
                weighted_change += signal * weight
                total_weight += weight

        if total_weight == 0:
            return 0.0
        return max(-1.0, min(1.0, weighted_change / total_weight))

    def _classify_trend(self, headline: float, core: float,
                        momentum: float) -> InflationTrend:
        """Classify inflation trend from headline and momentum."""
        if headline < self._DEFLATION_THRESHOLD:
            return InflationTrend.DEFLATIONARY

        if momentum > 0.6:
            return InflationTrend.RAPIDLY_RISING
        elif momentum > self._RISING_THRESHOLD:
            return InflationTrend.RISING
        elif momentum > 0.1:
            return InflationTrend.MODERATELY_RISING
        elif momentum > -0.1:
            return InflationTrend.STABLE
        elif momentum > self._COOLING_THRESHOLD:
            return InflationTrend.MODERATELY_COOLING
        elif momentum > -0.6:
            return InflationTrend.COOLING
        else:
            return InflationTrend.RAPIDLY_COOLING

    def _classify_regime(self, headline: float,
                         momentum: float) -> InflationRegime:
        """Classify inflation regime."""
        if headline >= self._EXTREME_INFLATION:
            return InflationRegime.HYPERINFLATION
        if headline < self._DEFLATION_THRESHOLD:
            return InflationRegime.DEFLATION
        if momentum > 0.2 and headline > self._HIGH_INFLATION:
            return InflationRegime.STAGFLATION
        if momentum > 0.2:
            return InflationRegime.REACCELERATION
        if momentum < -0.1:
            return InflationRegime.DISINFLATION
        return InflationRegime.STABLE_INFLATION

    def _compute_confidence(self, snapshot: MacroDataSnapshot) -> float:
        """Compute analysis confidence based on data completeness."""
        available = sum(1 for name in self._COMPONENT_WEIGHTS if snapshot.get(name))
        total = len(self._COMPONENT_WEIGHTS)
        base = available / total if total > 0 else 0.3
        return min(0.95, max(0.3, base))

    def _compute_leading_signals(self, snapshot: MacroDataSnapshot) -> dict[str, float]:
        """Compute signals from leading inflation indicators."""
        signals: dict[str, float] = {}

        leading_map = {
            "PPI": snapshot.get("PPI"),
            "Commodity_Index": snapshot.get("Commodity_Index"),
            "Wage_Growth": snapshot.get("Wage_Growth"),
            "ISM_Prices_Paid": snapshot.get("ISM_Prices_Paid"),
            "Import_Prices": snapshot.get("Import_Prices"),
        }

        for name, ind in leading_map.items():
            if ind is not None and ind.change is not None:
                signals[name] = min(1.0, max(-1.0, ind.change / 0.5))

        return signals

    def _extract_components(self, snapshot: MacroDataSnapshot) -> dict[str, float]:
        """Extract component values for detail reporting."""
        return {
            name: snapshot.get(name).value
            for name in self._COMPONENT_WEIGHTS
            if snapshot.get(name)
        }

    @staticmethod
    def _infer_direction(name: str) -> "IndicatorDirection":
        """CPI/PPI/Wage rising is negative for markets, commodity depends."""
        upper = name.upper()
        if any(k in upper for k in ("CPI", "PCE", "PPI", "WAGE")):
            from .data import IndicatorDirection
            return IndicatorDirection.NEGATIVE
        from .data import IndicatorDirection
        return IndicatorDirection.NEUTRAL


__all__ = [
    "InflationTrend",
    "InflationRegime",
    "InflationAnalysis",
    "InflationAnalyzer",
]
