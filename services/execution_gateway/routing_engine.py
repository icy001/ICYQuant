"""Routing Engine — Core routing decision engine for the SOR.

Evaluates routing candidates against active policies and strategies
to produce optimal execution path decisions. Supports multi-criteria
optimization with configurable weights.

Decision Process::

    Candidates → Score Calculation → Ranking → Best Venue

Usage::

    engine = RoutingEngine()
    engine.set_weights(latency=0.3, liquidity=0.4, cost=0.3)
    decision = await engine.evaluate(venues, context)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from services.execution_gateway.venue_registry import Venue

logger = logging.getLogger(__name__)


@dataclass
class RoutingScore:
    """Multi-factor routing score for a venue.

    Attributes:
        venue: Venue name
        total: Weighted total score (0-1)
        liquidity: Liquidity score component
        latency: Latency score component
        cost: Cost score component
        quality: Historical execution quality component
        reliability: Connection reliability score
        components: Detailed score breakdown
    """

    venue: str = ""
    total: float = 0.0
    liquidity: float = 0.0
    latency: float = 0.0
    cost: float = 0.0
    quality: float = 0.0
    reliability: float = 0.0
    components: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "venue": self.venue,
            "total": self.total,
            "liquidity": self.liquidity,
            "latency": self.latency,
            "cost": self.cost,
            "quality": self.quality,
            "reliability": self.reliability,
            "components": self.components,
        }


class RoutingEngine:
    """Multi-criteria routing decision engine.

    Computes weighted scores for each candidate venue and ranks them
    according to the active routing policy and weights.

    Attributes:
        weights: Factor weights for scoring
        _min_liquidity_threshold: Minimum liquidity score to consider
        _max_latency_ms: Maximum acceptable latency
        _max_cost_bps: Maximum acceptable cost in bps
    """

    def __init__(self) -> None:
        # Default weights: liquidity is most important
        self.weights: dict[str, float] = {
            "liquidity": 0.40,
            "cost": 0.25,
            "latency": 0.15,
            "quality": 0.10,
            "reliability": 0.10,
        }

        self._min_liquidity_threshold = 0.1
        self._max_latency_ms = 500.0
        self._max_cost_bps = 20.0

    # ── Configuration ──────────────────────────────────────────────

    def set_weights(
        self,
        liquidity: float = 0.40,
        cost: float = 0.25,
        latency: float = 0.15,
        quality: float = 0.10,
        reliability: float = 0.10,
    ) -> None:
        """Set routing factor weights.

        Args:
            liquidity: Weight for liquidity score (0-1)
            cost: Weight for cost score (0-1)
            latency: Weight for latency score (0-1)
            quality: Weight for quality score (0-1)
            reliability: Weight for reliability score (0-1)
        """
        total = liquidity + cost + latency + quality + reliability
        if total > 0:
            self.weights = {
                "liquidity": liquidity / total,
                "cost": cost / total,
                "latency": latency / total,
                "quality": quality / total,
                "reliability": reliability / total,
            }
        logger.info("Routing weights updated: %s", self.weights)

    # ── Evaluation ─────────────────────────────────────────────────

    async def evaluate(
        self,
        venues: list[Venue],
        liquidity_scores: Optional[dict[str, dict[str, Any]]] = None,
        urgency: str = "normal",
        context: Optional[dict[str, Any]] = None,
    ) -> list[RoutingScore]:
        """Evaluate and score candidate venues.

        Computes weighted scores for each venue and returns them
        sorted by total score (descending).

        Args:
            venues: Candidate venue list
            liquidity_scores: Pre-computed liquidity scores per venue
            urgency: Order urgency (normal, urgent, passive)
            context: Additional evaluation context

        Returns:
            Sorted list of RoutingScore objects
        """
        scores: list[RoutingScore] = []

        for venue in venues:
            # Compute component scores
            liquidity = self._compute_liquidity_score(
                venue, liquidity_scores.get(venue.name, {}) if liquidity_scores else {}
            )
            latency = self._compute_latency_score(venue)
            cost = self._compute_cost_score(venue)
            quality = self._compute_quality_score(venue)
            reliability = self._compute_reliability_score(venue)

            # Apply urgency adjustments
            if urgency == "urgent":
                latency *= 1.5  # Latency matters more for urgent orders
            elif urgency == "passive":
                cost *= 1.5  # Cost matters more for passive orders

            # Weighted total
            total = (
                liquidity * self.weights["liquidity"]
                + cost * self.weights["cost"]
                + latency * self.weights["latency"]
                + quality * self.weights["quality"]
                + reliability * self.weights["reliability"]
            )

            # Filter out venues below minimum liquidity
            if liquidity < self._min_liquidity_threshold:
                total *= 0.5  # Penalize but don't exclude

            scores.append(RoutingScore(
                venue=venue.name,
                total=total,
                liquidity=liquidity,
                latency=latency,
                cost=cost,
                quality=quality,
                reliability=reliability,
                components={
                    "liquidity": liquidity,
                    "latency": latency,
                    "cost": cost,
                    "quality": quality,
                    "reliability": reliability,
                },
            ))

        # Sort by total score descending
        scores.sort(key=lambda s: s.total, reverse=True)
        return scores

    async def select_best(
        self,
        scores: list[RoutingScore],
    ) -> RoutingScore:
        """Select the best venue from scored candidates.

        Args:
            scores: Sorted list of RoutingScore objects

        Returns:
            Best RoutingScore
        """
        if not scores:
            return RoutingScore()

        # Return highest-scored venue
        best = scores[0]
        logger.info(
            "Best venue: %s (score=%.3f, liq=%.3f, cost=%.3f, lat=%.3f)",
            best.venue,
            best.total,
            best.liquidity,
            best.cost,
            best.latency,
        )
        return best

    # ── Component Scoring ──────────────────────────────────────────

    def _compute_liquidity_score(
        self,
        venue: Venue,
        liquidity_data: dict[str, Any],
    ) -> float:
        """Compute liquidity score for a venue.

        Args:
            venue: Venue to score
            liquidity_data: Liquidity metrics

        Returns:
            Liquidity score (0-1)
        """
        score = liquidity_data.get("score", venue.liquidity_score)
        return min(max(score, 0.0), 1.0)

    def _compute_latency_score(self, venue: Venue) -> float:
        """Compute latency score for a venue.

        Args:
            venue: Venue to score

        Returns:
            Latency score (0-1), higher is better (lower latency)
        """
        if venue.avg_latency_ms <= 0:
            return 0.5
        # Normalize: 1ms → 1.0, 100ms → 0.5, 500ms → 0.0
        score = max(0.0, 1.0 - venue.avg_latency_ms / self._max_latency_ms)
        return min(score, 1.0)

    def _compute_cost_score(self, venue: Venue) -> float:
        """Compute cost score for a venue.

        Args:
            venue: Venue to score

        Returns:
            Cost score (0-1), higher is better (lower cost)
        """
        if venue.fee_bps < 0:
            return 0.5
        score = max(0.0, 1.0 - venue.fee_bps / self._max_cost_bps)
        return min(score, 1.0)

    def _compute_quality_score(self, venue: Venue) -> float:
        """Compute historical execution quality score.

        Args:
            venue: Venue to score

        Returns:
            Quality score (0-1)
        """
        return min(max(venue.quality_score, 0.0), 1.0)

    def _compute_reliability_score(self, venue: Venue) -> float:
        """Compute connection reliability score.

        Args:
            venue: Venue to score

        Returns:
            Reliability score (0-1)
        """
        return min(max(venue.reliability_score, 0.0), 1.0)

    def to_dict(self) -> dict[str, Any]:
        """Serialize engine state."""
        return {
            "weights": self.weights,
            "min_liquidity_threshold": self._min_liquidity_threshold,
            "max_latency_ms": self._max_latency_ms,
            "max_cost_bps": self._max_cost_bps,
        }
