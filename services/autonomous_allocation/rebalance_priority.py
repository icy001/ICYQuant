"""Rebalance Priority — assigns priority to rebalance instructions.

Priority is determined by:
1. Risk reduction urgency
2. Alpha improvement potential
3. Capacity efficiency
4. Liquidity quality
5. Execution cost economy
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Any, Dict, List, Optional


class PriorityLevel(IntEnum):
    """Rebalance priority levels."""
    EMERGENCY = 0
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    MINIMAL = 5


@dataclass
class RebalancePriorityScore:
    """Priority score for a rebalance instruction."""
    strategy_id: str
    total_score: float = 0.0
    risk_reduction_score: float = 0.0
    alpha_improvement_score: float = 0.0
    capacity_efficiency_score: float = 0.0
    liquidity_score: float = 0.0
    cost_economy_score: float = 0.0
    priority_level: PriorityLevel = PriorityLevel.MEDIUM
    rank: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)


class RebalancePriority:
    """Assigns priority scores to rebalance instructions.

    Determines which rebalances should be executed first.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._risk_weight = self._config.get("risk_weight", 0.30)
        self._alpha_weight = self._config.get("alpha_weight", 0.25)
        self._capacity_weight = self._config.get("capacity_weight", 0.20)
        self._liquidity_weight = self._config.get("liquidity_weight", 0.15)
        self._cost_weight = self._config.get("cost_weight", 0.10)

    def score(self, strategy_id: str,
              risk_score: float = 0.5,
              alpha_score: float = 0.5,
              capacity_score: float = 0.5,
              liquidity_score: float = 0.5,
              cost_score: float = 0.5,
              is_decrease: bool = False) -> RebalancePriorityScore:
        """Compute rebalance priority score.

        Higher score = higher priority.
        Decreases (risk-reducing) get a boost.
        """
        # For decreases, risk reduction is more important
        rw = self._risk_weight
        if is_decrease:
            rw = self._risk_weight * 1.3  # Boost risk reduction priority

        # Normalize: higher scores = higher priority
        total = (
            rw * risk_score +
            self._alpha_weight * alpha_score +
            self._capacity_weight * capacity_score +
            self._liquidity_weight * liquidity_score +
            self._cost_weight * cost_score
        )

        # Determine level
        if total > 0.85:
            level = PriorityLevel.EMERGENCY
        elif total > 0.75:
            level = PriorityLevel.CRITICAL
        elif total > 0.65:
            level = PriorityLevel.HIGH
        elif total > 0.50:
            level = PriorityLevel.MEDIUM
        elif total > 0.30:
            level = PriorityLevel.LOW
        else:
            level = PriorityLevel.MINIMAL

        return RebalancePriorityScore(
            strategy_id=strategy_id,
            total_score=total,
            risk_reduction_score=risk_score,
            alpha_improvement_score=alpha_score,
            capacity_efficiency_score=capacity_score,
            liquidity_score=liquidity_score,
            cost_economy_score=cost_score,
            priority_level=level,
        )

    def rank(self, scores: List[RebalancePriorityScore]) -> List[RebalancePriorityScore]:
        """Rank by priority (highest first)."""
        sorted_scores = sorted(scores, key=lambda s: s.total_score, reverse=True)
        for i, s in enumerate(sorted_scores):
            s.rank = i + 1
        return sorted_scores

    def get_highest_priority(self, scores: List[RebalancePriorityScore]
                              ) -> Optional[RebalancePriorityScore]:
        """Get the highest priority rebalance."""
        ranked = self.rank(scores)
        return ranked[0] if ranked else None
