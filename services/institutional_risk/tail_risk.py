"""TailRiskEngine — unified tail risk analysis.

Manages gap risk, crash risk, liquidity tail, correlation tail,
volatility tail, and execution tail — producing a composite
tail risk score.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class TailRiskCategory(Enum):
    GAP = auto()
    CRASH = auto()
    LIQUIDITY = auto()
    CORRELATION = auto()
    VOLATILITY = auto()
    EXECUTION = auto()


@dataclass
class TailRiskComponent:
    """A single tail risk component."""

    category: TailRiskCategory
    score: float = 0.0  # 0-100
    severity: str = "LOW"
    description: str = ""
    metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class TailRiskReport:
    """Comprehensive tail risk report."""

    entity_id: str
    overall_score: float = 0.0
    components: Dict[TailRiskCategory, TailRiskComponent] = field(default_factory=dict)
    risk_level: str = "LOW"
    worst_category: Optional[TailRiskCategory] = None
    worst_score: float = 0.0
    warnings: List[str] = field(default_factory=list)


class TailRiskEngine:
    """Unified tail risk analysis engine.

    Aggregates multiple tail risk categories into a composite score,
    helping identify where extreme risks are concentrated.

    Usage::

        engine = TailRiskEngine()
        report = engine.analyze(
            entity_id="capital",
            gap_risk=15.0,
            crash_risk=25.0,
            liquidity_tail=35.0,
        )
        print(f"Tail risk score: {report.overall_score}/100")
    """

    def __init__(
        self,
        score_threshold_medium: float = 30.0,
        score_threshold_high: float = 60.0,
        score_threshold_extreme: float = 80.0,
    ):
        self._medium = score_threshold_medium
        self._high = score_threshold_high
        self._extreme = score_threshold_extreme

    def analyze(
        self,
        entity_id: str,
        gap_risk: float = 0.0,
        crash_risk: float = 0.0,
        liquidity_tail: float = 0.0,
        correlation_tail: float = 0.0,
        volatility_tail: float = 0.0,
        execution_tail: float = 0.0,
        metrics: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> TailRiskReport:
        """Analyze tail risk across all categories.

        Args:
            entity_id: strategy/portfolio/capital pool id
            gap_risk: gap risk score (0-100)
            crash_risk: crash risk score (0-100)
            liquidity_tail: liquidity tail score (0-100)
            correlation_tail: correlation tail score (0-100)
            volatility_tail: volatility tail score (0-100)
            execution_tail: execution tail score (0-100)
            metrics: optional per-category metrics
        """
        components: Dict[TailRiskCategory, TailRiskComponent] = {}

        def _add(category: TailRiskCategory, score: float, desc: str):
            severity = self._severity(score)
            meta = metrics.get(category.name, {}) if metrics else {}
            components[category] = TailRiskComponent(
                category=category,
                score=score,
                severity=severity,
                description=desc,
                metrics=meta,
            )

        _add(TailRiskCategory.GAP, gap_risk, "Overnight/event gap risk")
        _add(TailRiskCategory.CRASH, crash_risk, "Market crash tail risk")
        _add(TailRiskCategory.LIQUIDITY, liquidity_tail, "Liquidity evaporation tail risk")
        _add(TailRiskCategory.CORRELATION, correlation_tail, "Correlation convergence tail risk")
        _add(TailRiskCategory.VOLATILITY, volatility_tail, "Volatility spike tail risk")
        _add(TailRiskCategory.EXECUTION, execution_tail, "Execution failure tail risk")

        # weighted composite (liquidity and correlation get higher weight in tails)
        weights = {
            TailRiskCategory.GAP: 1.0,
            TailRiskCategory.CRASH: 1.5,
            TailRiskCategory.LIQUIDITY: 2.0,
            TailRiskCategory.CORRELATION: 1.5,
            TailRiskCategory.VOLATILITY: 1.0,
            TailRiskCategory.EXECUTION: 1.0,
        }

        total_weight = sum(weights.values())
        overall = (
            sum(components[c].score * weights[c] for c in components) / total_weight
            if total_weight > 0 else 0.0
        )

        # worst category
        worst_cat = max(components.items(), key=lambda x: x[1].score)
        worst_cat_key = worst_cat[0]
        worst_cat_score = worst_cat[1].score

        # risk level
        risk_level = self._severity(overall)

        # warnings
        warnings = []
        for cat, comp in components.items():
            if comp.score >= self._high:
                warnings.append(f"{cat.name} tail risk HIGH: {comp.score:.0f}")
            elif comp.score >= self._medium:
                warnings.append(f"{cat.name} tail risk MEDIUM: {comp.score:.0f}")

        return TailRiskReport(
            entity_id=entity_id,
            overall_score=overall,
            components=components,
            risk_level=risk_level,
            worst_category=worst_cat_key,
            worst_score=worst_cat_score,
            warnings=warnings,
        )

    def _severity(self, score: float) -> str:
        if score >= self._extreme:
            return "EXTREME"
        if score >= self._high:
            return "HIGH"
        if score >= self._medium:
            return "MEDIUM"
        return "LOW"

    def compute_gap_risk(
        self,
        overnight_exposure_pct: float,
        max_historical_gap_pct: float,
        current_volatility: float,
    ) -> float:
        """Compute gap risk score.

        Considers overnight exposure as fraction of capital and
        historical worst-case gap.
        """
        score = overnight_exposure_pct * 0.5
        score += max_historical_gap_pct * 2.0
        score += current_volatility * 0.3
        return min(100.0, score)

    def compute_crash_risk(
        self,
        var_99_pct: float,
        tail_ratio: float,
        drawdown_pct: float,
    ) -> float:
        """Compute crash risk score."""
        score = var_99_pct * 1.5
        score += (tail_ratio - 1.0) * 50.0  # tail fatness
        score += drawdown_pct * 0.5
        return min(100.0, max(0.0, score))
