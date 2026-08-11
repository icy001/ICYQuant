"""Execution Quality — Execution quality analysis and scoring.

Analyzes execution quality using industry-standard metrics including:
    - Arrival Price comparison
    - Implementation Shortfall
    - VWAP comparison
    - Market impact estimation
    - Quality scoring

Quality Score: 0-100 scale
    90-100: Excellent execution
    70-89:  Good execution
    50-69:  Average execution
    30-49:  Below average
    0-29:   Poor execution

Usage::

    analyzer = ExecutionQualityAnalyzer()
    score = analyzer.compute_score(
        average_price=150.05,
        benchmark_price=150.00,
        vwap=150.02,
        quantity=10000,
        market_volume=1000000,
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class QualityScore:
    """Execution quality score with component breakdown.

    Attributes:
        overall: Overall quality score (0-100)
        arrival_price_component: Score for arrival price comparison
        vwap_component: Score for VWAP comparison
        timing_component: Score for execution timing
        market_impact_component: Score for market impact estimation
        rating: Text rating (Excellent, Good, Average, etc.)
    """

    overall: float = 0.0
    arrival_price_component: float = 0.0
    vwap_component: float = 0.0
    timing_component: float = 0.0
    market_impact_component: float = 0.0
    rating: str = "N/A"

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall,
            "arrival_price": self.arrival_price_component,
            "vwap": self.vwap_component,
            "timing": self.timing_component,
            "market_impact": self.market_impact_component,
            "rating": self.rating,
        }


@dataclass
class QualityMetrics:
    """Detailed execution quality metrics."""

    average_price: float = 0.0
    benchmark_price: float = 0.0
    market_vwap: float = 0.0
    quantity: float = 0.0
    market_volume: float = 0.0
    duration_seconds: float = 0.0
    arrival_slippage_bps: float = 0.0
    vwap_slippage_bps: float = 0.0
    implementation_shortfall_bps: float = 0.0
    participation_rate: float = 0.0
    estimated_impact_bps: float = 0.0
    quality_score: QualityScore = field(default_factory=QualityScore)

    def to_dict(self) -> dict[str, Any]:
        return {
            "average_price": self.average_price,
            "benchmark_price": self.benchmark_price,
            "market_vwap": self.market_vwap,
            "quantity": self.quantity,
            "market_volume": self.market_volume,
            "duration_seconds": self.duration_seconds,
            "arrival_slippage_bps": self.arrival_slippage_bps,
            "vwap_slippage_bps": self.vwap_slippage_bps,
            "implementation_shortfall_bps": self.implementation_shortfall_bps,
            "participation_rate": self.participation_rate,
            "estimated_impact_bps": self.estimated_impact_bps,
            "quality_score": self.quality_score.to_dict(),
        }


class ExecutionQualityAnalyzer:
    """Execution quality analysis and scoring engine.

    Computes industry-standard execution quality metrics including
    implementation shortfall, market impact estimation, and quality
    scoring on a 0-100 scale.

    Scoring Methodology:
        - Arrival Price comparison (40% weight)
        - VWAP comparison (30% weight)
        - Market Impact (20% weight)
        - Timing efficiency (10% weight)
    """

    # Scoring weights
    ARRIVAL_WEIGHT = 0.40
    VWAP_WEIGHT = 0.30
    IMPACT_WEIGHT = 0.20
    TIMING_WEIGHT = 0.10

    def compute_metrics(
        self,
        average_price: float,
        benchmark_price: float,
        market_vwap: float = 0.0,
        quantity: float = 0.0,
        market_volume: float = 0.0,
        duration_seconds: float = 0.0,
    ) -> QualityMetrics:
        """Compute comprehensive quality metrics.

        Args:
            average_price: Volume-weighted average execution price
            benchmark_price: Arrival/benchmark price
            market_vwap: Market VWAP over the execution period
            quantity: Total executed quantity
            market_volume: Total market volume during execution
            duration_seconds: Execution duration

        Returns:
            QualityMetrics with all computed values
        """
        # Arrival slippage
        arrival_slippage = self._compute_slippage(average_price, benchmark_price)

        # VWAP slippage
        vwap_slippage = self._compute_slippage(average_price, market_vwap) if market_vwap > 0 else 0.0

        # Implementation shortfall (simplified)
        implementation_shortfall = arrival_slippage

        # Participation rate
        participation = (quantity / market_volume) if market_volume > 0 else 0.0

        # Estimated market impact (simplified square-root model)
        estimated_impact = self._estimate_market_impact(quantity, market_volume, participation)

        # Quality score
        score = self._compute_score(
            arrival_slippage,
            vwap_slippage,
            estimated_impact,
            duration_seconds,
            quantity,
        )

        return QualityMetrics(
            average_price=average_price,
            benchmark_price=benchmark_price,
            market_vwap=market_vwap,
            quantity=quantity,
            market_volume=market_volume,
            duration_seconds=duration_seconds,
            arrival_slippage_bps=arrival_slippage,
            vwap_slippage_bps=vwap_slippage,
            implementation_shortfall_bps=implementation_shortfall,
            participation_rate=participation,
            estimated_impact_bps=estimated_impact,
            quality_score=score,
        )

    def compute_score(
        self,
        average_price: float,
        benchmark_price: float,
        vwap: float = 0.0,
        quantity: float = 0.0,
        market_volume: float = 0.0,
        duration_seconds: float = 0.0,
    ) -> QualityScore:
        """Compute execution quality score.

        Args:
            average_price: Average execution price
            benchmark_price: Arrival/benchmark price
            vwap: Market VWAP
            quantity: Executed quantity
            market_volume: Market volume
            duration_seconds: Duration

        Returns:
            QualityScore (0-100)
        """
        arrival_slippage = self._compute_slippage(average_price, benchmark_price)
        vwap_slippage = self._compute_slippage(average_price, vwap) if vwap > 0 else 0.0
        participation = (quantity / market_volume) if market_volume > 0 else 0.0
        impact = self._estimate_market_impact(quantity, market_volume, participation)

        return self._compute_score(arrival_slippage, vwap_slippage, impact, duration_seconds, quantity)

    # ── Internal Scoring Logic ─────────────────────────────────────

    @staticmethod
    def _compute_slippage(execution_price: float, benchmark_price: float) -> float:
        """Compute slippage in basis points.

        Positive = worse than benchmark (slippage cost).
        """
        if benchmark_price <= 0:
            return 0.0
        return (execution_price - benchmark_price) / benchmark_price * 10000

    @staticmethod
    def _estimate_market_impact(
        quantity: float,
        market_volume: float,
        participation_rate: float,
    ) -> float:
        """Estimate market impact using simplified square-root model.

        Impact ~ sqrt(participation_rate) * spread_factor

        Args:
            quantity: Executed quantity
            market_volume: Market volume
            participation_rate: Market participation rate

        Returns:
            Estimated impact in basis points
        """
        if participation_rate <= 0 or quantity <= 0:
            return 0.0

        # Simplified square-root impact model
        # Impact scales with sqrt of participation rate
        import math
        base_impact = 5.0  # Base impact in bps at 1% participation
        return base_impact * math.sqrt(participation_rate * 100)

    @staticmethod
    def _score_component(value: float, threshold: float) -> float:
        """Score a single component on 0-100 scale.

        Uses a sigmoid-like decay: score decreases as value approaches threshold.

        Args:
            value: The measured value (bps, seconds, etc.)
            threshold: The threshold where score hits ~50

        Returns:
            Component score (0-100)
        """
        if value <= 0:
            return 100.0
        if threshold <= 0:
            return 100.0

        # Exponential decay scoring
        import math
        score = 100.0 * math.exp(-value / threshold)
        return max(0.0, min(100.0, score))

    def _compute_score(
        self,
        arrival_slippage: float,
        vwap_slippage: float,
        market_impact: float,
        duration_seconds: float,
        quantity: float,
    ) -> QualityScore:
        """Compute composite quality score.

        Args:
            arrival_slippage: Slippage vs arrival in bps
            vwap_slippage: Slippage vs VWAP in bps
            market_impact: Estimated impact in bps
            duration_seconds: Duration in seconds
            quantity: Executed quantity

        Returns:
            QualityScore
        """
        # Score each component
        arrival_score = self._score_component(abs(arrival_slippage), 10.0)  # 10 bps threshold
        vwap_score = self._score_component(abs(vwap_slippage), 10.0)
        impact_score = self._score_component(market_impact, 5.0)  # 5 bps threshold

        # Timing score: efficiency based on quantity and duration
        fill_rate = (quantity / max(duration_seconds, 1)) * 60  # qty/min
        timing_score = min(100.0, fill_rate / 1000 * 100)  # 1000 qty/min = 100

        # Weighted composite
        overall = (
            self.ARRIVAL_WEIGHT * arrival_score
            + self.VWAP_WEIGHT * vwap_score
            + self.IMPACT_WEIGHT * impact_score
            + self.TIMING_WEIGHT * timing_score
        )

        # Determine rating
        if overall >= 90:
            rating = "Excellent"
        elif overall >= 70:
            rating = "Good"
        elif overall >= 50:
            rating = "Average"
        elif overall >= 30:
            rating = "Below Average"
        else:
            rating = "Poor"

        return QualityScore(
            overall=round(overall, 1),
            arrival_price_component=round(arrival_score, 1),
            vwap_component=round(vwap_score, 1),
            timing_component=round(timing_score, 1),
            market_impact_component=round(impact_score, 1),
            rating=rating,
        )

    def compare_strategies(
        self,
        strategy_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Compare execution quality across strategies.

        Args:
            strategy_results: List of dicts with strategy name and metrics

        Returns:
            Comparison dictionary
        """
        comparisons = []
        for result in strategy_results:
            metrics = self.compute_metrics(
                average_price=result.get("average_price", 0),
                benchmark_price=result.get("benchmark_price", 0),
                market_vwap=result.get("market_vwap", 0),
                quantity=result.get("quantity", 0),
                market_volume=result.get("market_volume", 0),
                duration_seconds=result.get("duration_seconds", 0),
            )
            comparisons.append({
                "strategy": result.get("strategy", "Unknown"),
                "metrics": metrics.to_dict(),
            })

        # Rank by quality score
        comparisons.sort(
            key=lambda c: c["metrics"]["quality_score"]["overall"],
            reverse=True,
        )

        return {
            "rankings": comparisons,
            "best_strategy": comparisons[0]["strategy"] if comparisons else "N/A",
            "best_score": comparisons[0]["metrics"]["quality_score"]["overall"] if comparisons else 0.0,
        }
