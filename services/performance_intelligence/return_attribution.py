"""Return Attribution Engine - decomposes returns into component sources."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ReturnSource(str, Enum):
    ASSET_SELECTION = "ASSET_SELECTION"
    MARKET_TIMING = "MARKET_TIMING"
    FACTOR_EXPOSURE = "FACTOR_EXPOSURE"
    STRATEGY_SIGNAL = "STRATEGY_SIGNAL"
    SECTOR_ALLOCATION = "SECTOR_ALLOCATION"
    CURRENCY = "CURRENCY"
    RESIDUAL = "RESIDUAL"


class AttributionLevel(str, Enum):
    PORTFOLIO = "PORTFOLIO"
    SECTOR = "SECTOR"
    ASSET = "ASSET"
    STRATEGY = "STRATEGY"


@dataclass
class AttributionComponent:
    source: ReturnSource
    contribution: float
    weight: float
    return_contribution: float
    explanation: str


@dataclass
class AttributionReport:
    report_id: str
    period: str
    total_return: float
    components: List[AttributionComponent]
    level: AttributionLevel
    confidence: float


class ReturnAttributionEngine:
    """Return Attribution Engine.

    Answers: Where did the returns come from?
    Decomposes returns into: Asset Selection, Market Timing, Factor Exposure, Strategy Signal.
    """

    def __init__(self):
        self.reports: List[AttributionReport] = []

    def analyze(self, returns) -> Dict[str, Any]:
        """Analyze returns and attribute them to sources.

        Args:
            returns: Returns data to analyze.

        Returns:
            Dict with attribution analysis.
        """
        if isinstance(returns, dict):
            return self._analyze_from_dict(returns)
        return {"attribution": returns}

    def _analyze_from_dict(self, returns: Dict[str, Any]) -> Dict[str, Any]:
        """Perform return attribution from structured data."""
        total_return = returns.get("total_return", 0.0)
        positions = returns.get("positions", [])
        benchmark_return = returns.get("benchmark_return", 0.0)
        factor_exposures = returns.get("factor_exposures", {})

        components = []

        # Asset Selection contribution
        selection_contribution = self._compute_selection_contribution(positions, benchmark_return)
        components.append(AttributionComponent(
            source=ReturnSource.ASSET_SELECTION,
            contribution=selection_contribution,
            weight=0.30,
            return_contribution=selection_contribution * total_return if total_return != 0 else 0.0,
            explanation=f"Asset selection contributed {selection_contribution:.2%} to return",
        ))

        # Market Timing contribution
        timing_contribution = self._compute_timing_contribution(positions)
        components.append(AttributionComponent(
            source=ReturnSource.MARKET_TIMING,
            contribution=timing_contribution,
            weight=0.20,
            return_contribution=timing_contribution * total_return if total_return != 0 else 0.0,
            explanation=f"Market timing contributed {timing_contribution:.2%} to return",
        ))

        # Factor Exposure contribution
        factor_contribution = self._compute_factor_contribution(factor_exposures)
        components.append(AttributionComponent(
            source=ReturnSource.FACTOR_EXPOSURE,
            contribution=factor_contribution,
            weight=0.25,
            return_contribution=factor_contribution * total_return if total_return != 0 else 0.0,
            explanation=f"Factor exposure contributed {factor_contribution:.2%} to return",
        ))

        # Strategy Signal contribution
        signal_contribution = self._compute_signal_contribution(positions)
        components.append(AttributionComponent(
            source=ReturnSource.STRATEGY_SIGNAL,
            contribution=signal_contribution,
            weight=0.15,
            return_contribution=signal_contribution * total_return if total_return != 0 else 0.0,
            explanation=f"Strategy signal contributed {signal_contribution:.2%} to return",
        ))

        # Residual
        total_contribution = sum(c.contribution for c in components)
        residual = 1.0 - total_contribution
        components.append(AttributionComponent(
            source=ReturnSource.RESIDUAL,
            contribution=residual,
            weight=0.10,
            return_contribution=residual * total_return if total_return != 0 else 0.0,
            explanation=f"Residual/unexplained portion: {residual:.2%}",
        ))

        report = AttributionReport(
            report_id=f"ATTR_{len(self.reports):04d}",
            period=returns.get("period", "DAILY"),
            total_return=total_return,
            components=components,
            level=returns.get("level", AttributionLevel.PORTFOLIO),
            confidence=1.0 - abs(residual),
        )
        self.reports.append(report)

        return {
            "attribution": returns,
            "total_return": total_return,
            "components": [
                {"source": c.source.value, "contribution": c.contribution,
                 "return_contribution": c.return_contribution, "explanation": c.explanation}
                for c in components
            ],
            "confidence": report.confidence,
            "dominant_source": max(components, key=lambda c: abs(c.contribution)).source.value,
        }

    def _compute_selection_contribution(self, positions: List[Dict], benchmark_return: float) -> float:
        if not positions:
            return 0.0
        weights = [p.get("weight", 0.0) for p in positions]
        asset_returns = [p.get("return", 0.0) for p in positions]
        total_weight = sum(weights)
        if total_weight == 0:
            return 0.0
        weighted_return = sum(w * r for w, r in zip(weights, asset_returns)) / total_weight
        excess = weighted_return - benchmark_return
        return max(-1.0, min(1.0, excess))

    def _compute_timing_contribution(self, positions: List[Dict]) -> float:
        if not positions:
            return 0.0
        timing_signals = [p.get("timing_score", 0.0) for p in positions]
        if not timing_signals:
            return 0.0
        return sum(timing_signals) / len(timing_signals)

    def _compute_factor_contribution(self, factor_exposures: Dict[str, float]) -> float:
        if not factor_exposures:
            return 0.0
        factor_returns = {
            "momentum": 0.06, "value": 0.03, "quality": 0.04,
            "low_vol": 0.02, "growth": 0.05, "size": 0.01,
        }
        total = 0.0
        for factor, exposure in factor_exposures.items():
            total += exposure * factor_returns.get(factor, 0.0)
        return max(-1.0, min(1.0, total))

    def _compute_signal_contribution(self, positions: List[Dict]) -> float:
        if not positions:
            return 0.0
        signal_strengths = [p.get("signal_strength", 0.0) for p in positions]
        if not signal_strengths:
            return 0.0
        return sum(signal_strengths) / len(signal_strengths)

    def get_latest_report(self) -> Optional[AttributionReport]:
        """Get the most recent attribution report."""
        return self.reports[-1] if self.reports else None

    def get_reports_by_period(self, period: str) -> List[AttributionReport]:
        """Get all reports for a specific period."""
        return [r for r in self.reports if r.period == period]
