"""
Strategy Conflict Resolver
==========================
Resolves conflicts when multiple strategies generate opposing signals
for the same instrument.

Resolution logic:
    Priority > Confidence > Signal Strength > Recency
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ConflictType(str, Enum):
    """Types of strategy conflicts."""

    OPPOSITE_DIRECTION = "opposite_direction"  # BUY vs SELL
    SAME_DIRECTION = "same_direction"          # BUY + BUY (need sizing merge)
    INSTRUMENT_LIMIT = "instrument_limit"       # Too many strategies on one instrument
    CAPITAL_CONTENTION = "capital_contention"   # Competing for limited capital


@dataclass
class ConflictResult:
    """Result of conflict resolution for a set of conflicting positions."""

    instrument: str = ""
    conflict_type: ConflictType = ConflictType.OPPOSITE_DIRECTION
    resolved: bool = False
    winning_strategy: str = ""
    losing_strategies: List[str] = field(default_factory=list)
    resolved_positions: List[Dict[str, Any]] = field(default_factory=list)
    rejected_positions: List[Dict[str, Any]] = field(default_factory=list)
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instrument": self.instrument,
            "conflict_type": self.conflict_type.value,
            "resolved": self.resolved,
            "winning_strategy": self.winning_strategy,
            "losing_strategies": self.losing_strategies,
            "resolved_count": len(self.resolved_positions),
            "rejected_count": len(self.rejected_positions),
            "reason": self.reason,
            "metadata": self.metadata,
        }


class StrategyConflictResolver:
    """
    Cross-Strategy Conflict Resolver.

    Detects and resolves conflicts when multiple strategies target
    the same instrument with potentially opposing directions.

    Resolution strategy:
    1. Group by instrument
    2. Detect conflicts (opposite directions)
    3. Resolve by: priority → confidence → strength → recency
    4. Net same-direction positions
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._initialized = False

        # Conflict resolution weights
        self._priority_weight = self._config.get("priority_weight", 0.40)
        self._confidence_weight = self._config.get("confidence_weight", 0.30)
        self._strength_weight = self._config.get("strength_weight", 0.20)
        self._recency_weight = self._config.get("recency_weight", 0.10)

        # Max strategies per instrument
        self._max_strategies_per_instrument = self._config.get("max_strategies_per_instrument", 5)

        # Conflict history
        self._conflict_history: List[ConflictResult] = []
        self._max_history = self._config.get("max_history", 1000) if config else 1000

        # Metrics
        self._metrics: Dict[str, int] = {}
        self.last_conflict_count: int = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("StrategyConflictResolver initialized")

    async def shutdown(self) -> None:
        self._conflict_history.clear()
        self._initialized = False
        logger.info("StrategyConflictResolver shut down")

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def _group_by_instrument(
        self,
        positions: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group positions by instrument."""
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for pos in positions:
            instrument = pos.get("instrument", "")
            if instrument:
                if instrument not in groups:
                    groups[instrument] = []
                groups[instrument].append(pos)
        return groups

    def _detect_conflict_type(
        self,
        positions: List[Dict[str, Any]],
    ) -> ConflictType:
        """Detect the type of conflict among positions for the same instrument."""
        directions: Set[str] = set()
        for pos in positions:
            direction = pos.get("direction", "").upper()
            # Normalize direction
            if direction in ("LONG", "BUY", "BUY_TO_OPEN"):
                directions.add("LONG")
            elif direction in ("SHORT", "SELL", "SELL_TO_OPEN"):
                directions.add("SHORT")

        if len(directions) > 1:
            return ConflictType.OPPOSITE_DIRECTION

        if len(positions) > self._max_strategies_per_instrument:
            return ConflictType.INSTRUMENT_LIMIT

        return ConflictType.SAME_DIRECTION

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def _compute_score(self, pos: Dict[str, Any]) -> float:
        """Compute a resolution score for a position."""
        priority = pos.get("priority", 50) / 100.0  # Normalize to 0-1
        confidence = pos.get("confidence", 0.0)
        strength = abs(pos.get("signal_strength", pos.get("strength", 0.0)))

        # Recency: prefer newer signals
        created_at = pos.get("created_at")
        if isinstance(created_at, datetime):
            age_seconds = (datetime.now(timezone.utc) - created_at).total_seconds()
            recency = max(0.0, 1.0 - age_seconds / 3600.0)  # Decay over 1 hour
        elif isinstance(created_at, str):
            try:
                created_dt = datetime.fromisoformat(created_at)
                age_seconds = (datetime.now(timezone.utc) - created_dt).total_seconds()
                recency = max(0.0, 1.0 - age_seconds / 3600.0)
            except (ValueError, TypeError):
                recency = 0.5
        else:
            recency = 0.5

        score = (
            priority * self._priority_weight
            + confidence * self._confidence_weight
            + min(strength, 1.0) * self._strength_weight
            + recency * self._recency_weight
        )
        return score

    def _resolve_opposite_direction(
        self,
        instrument: str,
        positions: List[Dict[str, Any]],
    ) -> ConflictResult:
        """Resolve opposite-direction conflicts: pick the winner."""
        longs = [p for p in positions if p.get("direction", "").upper() in ("LONG", "BUY", "BUY_TO_OPEN")]
        shorts = [p for p in positions if p.get("direction", "").upper() in ("SHORT", "SELL", "SELL_TO_OPEN")]

        # Score all positions
        scored_longs = [(self._compute_score(p), p) for p in longs]
        scored_shorts = [(self._compute_score(p), p) for p in shorts]

        if not scored_longs and not scored_shorts:
            return ConflictResult(
                instrument=instrument,
                conflict_type=ConflictType.OPPOSITE_DIRECTION,
                resolved=False,
                reason="No valid positions to resolve",
            )

        # Pick highest-scoring position overall
        all_scored = scored_longs + scored_shorts
        all_scored.sort(key=lambda x: -x[0])
        best_score, winner = all_scored[0]
        losers = [p for s, p in all_scored[1:]]

        winner_sid = winner.get("strategy_id", "")
        loser_sids = [p.get("strategy_id", "") for p in losers]

        return ConflictResult(
            instrument=instrument,
            conflict_type=ConflictType.OPPOSITE_DIRECTION,
            resolved=True,
            winning_strategy=winner_sid,
            losing_strategies=loser_sids,
            resolved_positions=[winner],
            rejected_positions=losers,
            reason=(
                f"Resolved {len(longs)}L vs {len(shorts)}S: "
                f"winner={winner_sid} (score={best_score:.3f})"
            ),
        )

    def _resolve_same_direction(
        self,
        instrument: str,
        positions: List[Dict[str, Any]],
    ) -> ConflictResult:
        """Resolve same-direction conflicts: merge or pick best."""
        if len(positions) == 1:
            return ConflictResult(
                instrument=instrument,
                conflict_type=ConflictType.SAME_DIRECTION,
                resolved=True,
                winning_strategy=positions[0].get("strategy_id", ""),
                resolved_positions=positions,
                reason="Single position, no conflict",
            )

        # For same direction, we can merge positions (sum quantities)
        # or pick the best one. Default: pick best by score.
        scored = [(self._compute_score(p), p) for p in positions]
        scored.sort(key=lambda x: -x[0])
        best_score, best = scored[0]
        others = [p for s, p in scored[1:]]

        # Merge: add quantities from other same-direction positions
        merged = dict(best)
        total_qty = best.get("quantity", best.get("position_size", 0.0))
        total_value = best.get("position_value", best.get("allocated_capital", 0.0))

        for other in others:
            total_qty += other.get("quantity", other.get("position_size", 0.0))
            total_value += other.get("position_value", other.get("allocated_capital", 0.0))

        merged["quantity"] = total_qty
        merged["position_size"] = total_qty
        merged["position_value"] = total_value
        merged["allocated_capital"] = total_value
        merged["merged_strategies"] = [p.get("strategy_id", "") for p in positions]

        return ConflictResult(
            instrument=instrument,
            conflict_type=ConflictType.SAME_DIRECTION,
            resolved=True,
            winning_strategy=best.get("strategy_id", ""),
            losing_strategies=[p.get("strategy_id", "") for p in others],
            resolved_positions=[merged],
            rejected_positions=others,
            reason=f"Merged {len(positions)} same-direction positions for {instrument}",
        )

    def _resolve_instrument_limit(
        self,
        instrument: str,
        positions: List[Dict[str, Any]],
    ) -> ConflictResult:
        """Resolve instrument limit: keep top N by score."""
        scored = [(self._compute_score(p), p) for p in positions]
        scored.sort(key=lambda x: -x[0])

        keep = [p for s, p in scored[:self._max_strategies_per_instrument]]
        drop = [p for s, p in scored[self._max_strategies_per_instrument:]]

        return ConflictResult(
            instrument=instrument,
            conflict_type=ConflictType.INSTRUMENT_LIMIT,
            resolved=True,
            winning_strategy=keep[0].get("strategy_id", "") if keep else "",
            losing_strategies=[p.get("strategy_id", "") for p in drop],
            resolved_positions=keep,
            rejected_positions=drop,
            reason=(
                f"Instrument limit: kept {len(keep)}/{len(positions)} "
                f"(max={self._max_strategies_per_instrument})"
            ),
        )

    # ------------------------------------------------------------------
    # Main Resolution
    # ------------------------------------------------------------------

    async def resolve(
        self,
        positions: List[Dict[str, Any]],
        portfolio_state: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Resolve strategy conflicts across all positions.

        Args:
            positions: List of position/allocation dicts.
            portfolio_state: Current portfolio state.

        Returns:
            Resolved list of positions (conflicts resolved, netted).
        """
        if not self._initialized:
            await self.initialize()

        groups = self._group_by_instrument(positions)
        resolved_all: List[Dict[str, Any]] = []
        conflicts_found = 0

        for instrument, group in groups.items():
            if len(group) == 1:
                # No conflict for single-position instruments
                resolved_all.extend(group)
                continue

            conflict_type = self._detect_conflict_type(group)
            conflicts_found += 1

            if conflict_type == ConflictType.OPPOSITE_DIRECTION:
                result = self._resolve_opposite_direction(instrument, group)
            elif conflict_type == ConflictType.INSTRUMENT_LIMIT:
                result = self._resolve_instrument_limit(instrument, group)
            else:
                result = self._resolve_same_direction(instrument, group)

            resolved_all.extend(result.resolved_positions)
            self._conflict_history.append(result)

            # Cap history
            if len(self._conflict_history) > self._max_history:
                self._conflict_history = self._conflict_history[-self._max_history:]

        # Add positions without instrument info (passthrough)
        for pos in positions:
            if not pos.get("instrument"):
                resolved_all.append(pos)

        self.last_conflict_count = conflicts_found
        self._metrics["conflicts_detected"] = self._metrics.get("conflicts_detected", 0) + conflicts_found
        self._metrics["conflicts_resolved"] = self._metrics.get("conflicts_resolved", 0) + len(resolved_all)

        logger.info(
            "Conflict resolution: %d conflicts found, %d positions resolved",
            conflicts_found,
            len(resolved_all),
        )

        return resolved_all

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def get_conflict_history(self, limit: int = 100) -> List[ConflictResult]:
        return self._conflict_history[-limit:]

    def get_metrics(self) -> Dict[str, Any]:
        return dict(self._metrics)

    @property
    def is_initialized(self) -> bool:
        return self._initialized
