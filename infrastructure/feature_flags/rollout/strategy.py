"""
Rollout strategy engine.

Combines segments and percentage-based
rollout to determine the effective rollout
policy for a given target.

Strategy:
    1. Match segments by priority
    2. Apply segment-specific percentage override
    3. Fall back to default percentage if no segment matches
    4. Apply consistent hashing for final assignment
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .assignment import StickyAssignment
from .rollout import RolloutAssignment, RolloutPolicy
from .segment import SegmentEngine


class RolloutStrategy:
    """
    Combined rollout strategy with segments and percentage.

    Orchestrates segment matching, percentage
    resolution, and sticky assignment to produce
    final rollout decisions.

    Pipeline:
        Target Attributes → Segment Match → Percentage Override
        → Consistent Hash → Sticky Assignment → Decision

    Usage:
        strategy = RolloutStrategy()
        strategy.set_policy(RolloutPolicy(percentage=10.0))
        strategy.segment_engine.add_segment(...)
        assignment = await strategy.evaluate(
            flag_key="new-risk",
            target_id="account_123",
            attributes={"broker": "IBKR"},
        )
    """

    def __init__(
        self,
        policy: Optional[RolloutPolicy] = None,
    ) -> None:
        """
        Initialize the rollout strategy.

        Args:
            policy: Default rollout policy.
        """
        self._policy = policy or RolloutPolicy()
        self._segment_engine = SegmentEngine()
        self._assignment = StickyAssignment()
        self._evaluation_count = 0
        self._segment_hits = 0
        self._direct_hits = 0

    def set_policy(self, policy: RolloutPolicy) -> None:
        """Set the default rollout policy."""
        self._policy = policy

    @property
    def segment_engine(self) -> SegmentEngine:
        """Access the segment engine for configuration."""
        return self._segment_engine

    @property
    def assignment_engine(self) -> StickyAssignment:
        """Access the sticky assignment engine."""
        return self._assignment

    async def evaluate(
        self,
        flag_key: str,
        target_id: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> RolloutAssignment:
        """
        Evaluate the rollout strategy for a target.

        1. Match segments to find percentage override
        2. Compute final percentage
        3. Perform sticky assignment

        Args:
            flag_key: Feature flag key.
            target_id: Target identifier.
            attributes: Target attributes for segment matching.

        Returns:
            RolloutAssignment with the decision.
        """
        self._evaluation_count += 1
        attrs = attributes or {}

        # Step 1: Match segments
        matched_segment = self._segment_engine.resolve(attrs)

        # Step 2: Resolve percentage
        effective_policy = self._policy
        if matched_segment and matched_segment.percentage is not None:
            effective_policy = RolloutPolicy(
                percentage=matched_segment.percentage,
                hash_key=self._policy.hash_key,
                enabled=self._policy.enabled,
                algorithm=self._policy.algorithm,
                max_buckets=self._policy.max_buckets,
                sticky=self._policy.sticky,
                description=f"segment:{matched_segment.segment_id}",
            )
            self._segment_hits += 1
        else:
            self._direct_hits += 1

        # Step 3: Sticky assignment
        assignment = await self._assignment.assign(
            flag_key=flag_key,
            target_id=target_id,
            policy=effective_policy,
            context_attributes=attrs,
        )

        # Add segment info
        if matched_segment:
            assignment.version = f"segment:{matched_segment.segment_id}"
        else:
            assignment.version = "default"

        return assignment

    async def evaluate_batch(
        self,
        flag_key: str,
        target_ids: List[str],
        attributes: Optional[Dict[str, Any]] = None,
    ) -> List[RolloutAssignment]:
        """Evaluate rollout for multiple targets."""
        return [
            await self.evaluate(flag_key, tid, attributes)
            for tid in target_ids
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get strategy statistics."""
        return {
            "evaluations": self._evaluation_count,
            "segment_hits": self._segment_hits,
            "direct_hits": self._direct_hits,
            "segment_hit_rate": (
                self._segment_hits / self._evaluation_count
                if self._evaluation_count > 0
                else 0.0
            ),
            "assignment_stats": self._assignment.get_stats(),
            "segment_stats": self._segment_engine.get_stats(),
        }

    def reset_stats(self) -> None:
        """Reset strategy statistics."""
        self._evaluation_count = 0
        self._segment_hits = 0
        self._direct_hits = 0
        self._assignment.reset_stats()
