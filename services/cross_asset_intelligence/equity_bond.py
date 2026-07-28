"""Equity-Bond Intelligence.

Analyzes the relationship between equity markets and bond markets,
including yield impact on valuations, credit spread signals,
and growth/value rotation driven by rate changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class EquityBondResult:
    """Result of equity-bond relationship analysis.

    Attributes:
        yield_10y: Current 10-year treasury yield.
        real_yield: Real yield (yield - inflation).
        credit_spread: Investment grade credit spread.
        equity_pressure: Pressure level on equities from bond market.
        growth_stock_pressure: Specific pressure on growth stocks.
        valuation_signal: Equity valuation signal from bond perspective.
        description: Human-readable summary.
        confidence: Analysis confidence.
        supporting_factors: Factors supporting the analysis.
        timestamp: Analysis timestamp.
    """

    yield_10y: float = 0.0
    real_yield: float = 0.0
    credit_spread: float = 0.0
    equity_pressure: str = "NEUTRAL"
    growth_stock_pressure: str = "NEUTRAL"
    valuation_signal: str = "FAIR"
    description: str = ""
    confidence: float = 0.5
    supporting_factors: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_equity_favorable(self) -> bool:
        return self.equity_pressure in ("LOW", "NEUTRAL")

    @property
    def is_equity_pressured(self) -> bool:
        return self.equity_pressure in ("HIGH", "CRITICAL")

    @property
    def is_growth_favorable(self) -> bool:
        return self.growth_stock_pressure in ("LOW", "NEUTRAL")


class EquityBondAnalyzer:
    """Analyzes equity-bond relationship dynamics.

    Evaluates how bond market conditions (yields, spreads, real rates)
    impact equity valuations, with special focus on growth vs value
    rotation signals.

    Attributes:
        yield_threshold_high: Yield level considered high for equities.
        yield_threshold_low: Yield level considered low/favorable.
        real_yield_neutral: Neutral real yield level.
        spread_threshold_wide: Credit spread level signaling stress.
    """

    def __init__(self) -> None:
        self.yield_threshold_high: float = 5.0
        self.yield_threshold_low: float = 3.0
        self.real_yield_neutral: float = 1.0
        self.spread_threshold_wide: float = 2.0
        self.yield_history: list[float] = []

    def analyze(self, data: dict[str, float] | None = None) -> dict[str, Any]:
        """Analyze equity-bond relationship from input data.

        Args:
            data: Dict with optional keys: yield_10y, real_yield, credit_spread.

        Returns:
            Dict with relationship analysis.
        """
        y10 = data.get("yield_10y", 4.0) if data else 4.0
        real = data.get("real_yield", 1.0) if data else 1.0
        spread = data.get("credit_spread", 1.0) if data else 1.0

        result = self.analyze_full(y10, real, spread)
        return {
            "equity_pressure": result.equity_pressure,
            "growth_stock_pressure": result.growth_stock_pressure,
            "risk": result.equity_pressure,
            "reason": result.description,
        }

    def analyze_full(
        self,
        yield_10y: float = 4.0,
        real_yield: float = 1.0,
        credit_spread: float = 1.0,
    ) -> EquityBondResult:
        """Full equity-bond analysis.

        Args:
            yield_10y: 10-year treasury yield (%).
            real_yield: Real yield (%).
            credit_spread: Investment grade credit spread (%).

        Returns:
            EquityBondResult.
        """
        self.yield_history.append(yield_10y)

        # Equity pressure from yields
        equity_pressure = self._assess_equity_pressure(yield_10y, real_yield, credit_spread)

        # Growth stock pressure
        growth_pressure = self._assess_growth_pressure(yield_10y, real_yield)

        # Valuation signal
        val_signal = self._assess_valuation(yield_10y, real_yield, credit_spread)

        # Supporting factors
        factors = self._collect_factors(yield_10y, real_yield, credit_spread)

        # Confidence
        confidence = self._compute_confidence(yield_10y, real_yield, credit_spread)

        # Description
        description = self._generate_description(equity_pressure, growth_pressure, yield_10y, real_yield, spread=credit_spread)

        return EquityBondResult(
            yield_10y=yield_10y,
            real_yield=real_yield,
            credit_spread=credit_spread,
            equity_pressure=equity_pressure,
            growth_stock_pressure=growth_pressure,
            valuation_signal=val_signal,
            description=description,
            confidence=confidence,
            supporting_factors=factors,
        )

    def get_yield_trend(self) -> str:
        """Get recent yield trend."""
        if len(self.yield_history) < 2:
            return "stable"
        mid = len(self.yield_history) // 2
        first = sum(self.yield_history[:mid]) / mid
        second = sum(self.yield_history[mid:]) / (len(self.yield_history) - mid)
        diff = second - first
        if diff > 0.3:
            return "rising"
        elif diff < -0.3:
            return "falling"
        return "stable"

    def _assess_equity_pressure(self, y10: float, real: float, spread: float) -> str:
        score = 0
        if y10 > self.yield_threshold_high:
            score += 2
        elif y10 > 4.0:
            score += 1
        if real > 2.0:
            score += 2
        elif real > 1.5:
            score += 1
        if spread > self.spread_threshold_wide:
            score += 2
        elif spread > 1.5:
            score += 1
        if y10 < self.yield_threshold_low:
            score -= 1
        if score >= 4:
            return "CRITICAL"
        elif score >= 2:
            return "HIGH"
        elif score >= 0:
            return "NEUTRAL"
        return "LOW"

    def _assess_growth_pressure(self, y10: float, real: float) -> str:
        score = 0
        if y10 > self.yield_threshold_high:
            score += 3
        elif y10 > 4.0:
            score += 2
        if real > 2.0:
            score += 3
        elif real > 1.5:
            score += 2
        if y10 < self.yield_threshold_low:
            score -= 2
        if score >= 4:
            return "CRITICAL"
        elif score >= 2:
            return "HIGH"
        elif score >= 0:
            return "NEUTRAL"
        return "LOW"

    def _assess_valuation(self, y10: float, real: float, spread: float) -> str:
        score = 0.0
        # Higher real yield = lower fair PE = stocks potentially overvalued
        score += (real - self.real_yield_neutral) * 2
        score += (y10 - 4.0) * 0.5
        score += (spread - 1.0) * 1.0
        if score > 2.0:
            return "OVERVAULED"
        elif score > 0.5:
            return "RICH"
        elif score > -0.5:
            return "FAIR"
        elif score > -2.0:
            return "ATTRACTIVE"
        return "CHEAP"

    def _collect_factors(self, y10: float, real: float, spread: float) -> list[str]:
        factors: list[str] = []
        if y10 > self.yield_threshold_high:
            factors.append("High nominal yields pressuring equity multiples")
        if real > 2.0:
            factors.append("High real yields challenging growth stock valuations")
        if spread > self.spread_threshold_wide:
            factors.append("Wide credit spreads signal risk aversion")
        if y10 < self.yield_threshold_low:
            factors.append("Low yields supportive of equity valuations")
        if real < 0.5:
            factors.append("Low/negative real yields favor risk assets")
        return factors

    def _compute_confidence(self, y10: float, real: float, spread: float) -> float:
        confidence = 0.4
        extremes = sum(1 for v in [y10, real, spread]
                       if v > 4.0 or v < 1.0)
        confidence += 0.15 * min(3, extremes)
        if len(self.yield_history) > 10:
            confidence += 0.1
        return min(1.0, confidence)

    def _generate_description(self, eq_p: str, g_p: str, y10: float, real: float, spread: float = 0.0) -> str:
        parts = [f"Y10={y10:.1f}%, Real={real:.1f}%"]
        if spread:
            parts.append(f"Spread={spread:.1f}%")
        parts.append(f"| Equity pressure: {eq_p}")
        parts.append(f"| Growth: {g_p}")
        return " ".join(parts)

    def clear(self) -> None:
        self.yield_history.clear()
