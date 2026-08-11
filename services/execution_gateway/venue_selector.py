"""Venue Selector — Optimal venue selection engine.

Selects the best execution venue based on routing policy, strategy,
liquidity analysis, and venue characteristics. Returns scored and
ranked venue selections.

Selection Process::

    Candidates → Filter → Score → Rank → Select Best

Usage::

    selector = VenueSelector()
    best = await selector.select(venues, liquidity_scores, policy, strategy)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from services.execution_gateway.routing_engine import RoutingEngine, RoutingScore
from services.execution_gateway.routing_policy import RoutingPolicy, RoutingPolicyType
from services.execution_gateway.routing_strategy import RoutingStrategy, RoutingStrategyType
from services.execution_gateway.venue_registry import Venue

logger = logging.getLogger(__name__)


@dataclass
class VenueSelection:
    """Selected venue with evaluation details.

    Attributes:
        name: Selected venue name
        broker_name: Associated broker
        score: Total weighted score
        rank: Rank among candidates
        scores: Detailed component scores
        reason: Selection rationale
        alternatives: Ranked alternative venues
    """

    name: str = ""
    broker_name: str = ""
    score: float = 0.0
    rank: int = 1
    scores: Optional[RoutingScore] = None
    reason: str = ""
    alternatives: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "broker_name": self.broker_name,
            "score": self.score,
            "rank": self.rank,
            "scores": self.scores.to_dict() if self.scores else {},
            "reason": self.reason,
            "alternatives": self.alternatives,
        }


class VenueSelector:
    """Venue selection engine.

    Evaluates candidate venues using the routing engine and selects
    the optimal venue based on policy and strategy.

    Attributes:
        routing_engine: Multi-criteria routing engine
        _selection_history: Recent venue selections
    """

    def __init__(self, routing_engine: Optional[RoutingEngine] = None) -> None:
        self.routing_engine = routing_engine or RoutingEngine()
        self._selection_history: list[VenueSelection] = []
        self._max_history = 500

    # ── Selection ──────────────────────────────────────────────────

    async def select(
        self,
        venues: list[Venue],
        liquidity_scores: Optional[dict[str, dict[str, Any]]] = None,
        policy: Optional[RoutingPolicy] = None,
        strategy: Optional[RoutingStrategy] = None,
        urgency: str = "normal",
        context: Optional[dict[str, Any]] = None,
    ) -> VenueSelection:
        """Select the best venue from candidates.

        Args:
            venues: Candidate venue list
            liquidity_scores: Liquidity analysis per venue
            policy: Active routing policy
            strategy: Active routing strategy
            urgency: Order urgency
            context: Additional context

        Returns:
            VenueSelection with selected venue
        """
        if not venues:
            logger.warning("No venues provided for selection")
            return VenueSelection(reason="No venues available")

        policy = policy or RoutingPolicy(RoutingPolicyType.BEST_EXECUTION)
        strategy = strategy or RoutingStrategy(RoutingStrategyType.DYNAMIC)

        # Apply policy weights
        if policy.policy_type != RoutingPolicyType.CUSTOM:
            self.routing_engine.set_weights(**policy.weights)

        # Filter venues
        filtered = self._filter_venues(venues, policy)

        if not filtered:
            logger.warning("All venues filtered out by policy")
            return VenueSelection(reason="No venues passed policy filter")

        # Score candidates
        scored = await self.routing_engine.evaluate(
            venues=filtered,
            liquidity_scores=liquidity_scores,
            urgency=urgency,
            context=context,
        )

        if not scored:
            return VenueSelection(reason="No scores computed")

        # Select best
        best = scored[0]
        selected_venue = next((v for v in venues if v.name == best.venue), None)

        if not selected_venue:
            return VenueSelection(reason=f"Selected venue {best.venue} not found")

        # Build selection
        selection = VenueSelection(
            name=best.venue,
            broker_name=selected_venue.broker_name,
            score=best.total,
            rank=1,
            scores=best,
            reason=f"Selected {best.venue}: score={best.total:.3f} "
                   f"(liq={best.liquidity:.2f}, cost={best.cost:.2f}, "
                   f"lat={best.latency:.2f})",
            alternatives=[s.venue for s in scored[1:4]],
        )

        self._record_selection(selection)

        logger.info(
            "Venue selected: %s (score=%.3f), alternatives: %s",
            selection.name,
            selection.score,
            selection.alternatives,
        )

        return selection

    async def select_parallel(
        self,
        venues: list[Venue],
        max_venues: int = 3,
        liquidity_scores: Optional[dict[str, dict[str, Any]]] = None,
    ) -> list[VenueSelection]:
        """Select multiple venues for parallel execution.

        Args:
            venues: Candidate venue list
            max_venues: Maximum venues to select
            liquidity_scores: Liquidity analysis per venue

        Returns:
            List of VenueSelection objects
        """
        if not venues:
            return []

        scored = await self.routing_engine.evaluate(
            venues=venues,
            liquidity_scores=liquidity_scores,
        )

        selections: list[VenueSelection] = []
        for rank, score in enumerate(scored[:max_venues], start=1):
            venue = next((v for v in venues if v.name == score.venue), None)
            if venue:
                selections.append(VenueSelection(
                    name=score.venue,
                    broker_name=venue.broker_name,
                    score=score.total,
                    rank=rank,
                    scores=score,
                    reason=f"Parallel venue #{rank}: {score.venue}",
                ))

        return selections

    # ── Filtering ──────────────────────────────────────────────────

    def _filter_venues(
        self,
        venues: list[Venue],
        policy: RoutingPolicy,
    ) -> list[Venue]:
        """Filter venues by policy constraints.

        Args:
            venues: Candidate venues
            policy: Active routing policy

        Returns:
            Filtered venue list
        """
        filtered = []

        for venue in venues:
            # Must be active
            if not venue.is_active():
                continue

            # Must meet minimum score threshold
            avg_score = (
                venue.liquidity_score * 0.4
                + venue.quality_score * 0.3
                + venue.reliability_score * 0.3
            )
            if avg_score < policy.min_score_threshold:
                continue

            filtered.append(venue)

        # Sort: prefer primary if configured
        if policy.prefer_primary:
            filtered.sort(
                key=lambda v: (1 if v.venue_type.value == "EXCHANGE" else 0),
                reverse=True,
            )

        return filtered[:policy.max_venues]

    # ── History ────────────────────────────────────────────────────

    def _record_selection(self, selection: VenueSelection) -> None:
        """Record a venue selection in history."""
        self._selection_history.append(selection)
        if len(self._selection_history) > self._max_history:
            self._selection_history = self._selection_history[-self._max_history:]

    def get_selection_history(self, limit: int = 100) -> list[VenueSelection]:
        """Get recent venue selections.

        Args:
            limit: Maximum number to return

        Returns:
            List of recent VenueSelection objects
        """
        return self._selection_history[-limit:]

    def to_dict(self) -> dict[str, Any]:
        """Serialize selector state."""
        return {
            "selections_count": len(self._selection_history),
            "engine": self.routing_engine.to_dict(),
        }
