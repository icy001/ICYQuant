"""
Percentage rollout engine.

Unified entry point for percentage-based
rollout evaluation. Coordinates segments,
consistent hashing, sticky assignment,
and progressive deployment to produce
final rollout decisions.

Pipeline:
    Feature → Segment Match → Percentage
    → Consistent Hash → Sticky Assignment → Decision
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

from .assignment import StickyAssignment
from .audit import RolloutAudit
from .cache import RolloutCache
from .hasher import ConsistentHasher
from .metrics import RolloutMetrics
from .progressive import ProgressiveRollout
from .rollout import RolloutAssignment, RolloutPolicy
from .segment import SegmentEngine
from .strategy import RolloutStrategy
from .validator import RolloutValidator


class RolloutEngine:
    """
    Unified percentage rollout engine.

    Orchestrates the full rollout evaluation
    pipeline from segment matching through
    percentage-based assignment.

    Usage:
        engine = RolloutEngine()
        policy = RolloutPolicy(percentage=10.0)
        engine.set_policy("new-risk", policy)

        result = await engine.evaluate(
            flag_key="new-risk",
            target_id="account_123",
            attributes={"broker": "IBKR"},
        )
        # result.assigned == True/False
    """

    def __init__(self) -> None:
        """Initialize the rollout engine."""
        self._strategies: Dict[str, RolloutStrategy] = {}
        self._policies: Dict[str, RolloutPolicy] = {}
        self._progressive_rollouts: Dict[str, ProgressiveRollout] = {}
        self._segment_engine = SegmentEngine()
        self._validator = RolloutValidator()
        self._cache = RolloutCache()
        self._metrics = RolloutMetrics()
        self._audit = RolloutAudit()
        self._hasher = ConsistentHasher()
        self._lock = asyncio.Lock()
        self._evaluation_count = 0
        self._error_count = 0

    async def evaluate(
        self,
        flag_key: str,
        target_id: str,
        attributes: Optional[Dict[str, Any]] = None,
        policy: Optional[RolloutPolicy] = None,
        use_cache: bool = True,
    ) -> RolloutAssignment:
        """
        Evaluate a rollout decision for a target.

        1. Resolve rollout policy (flag-specific or default)
        2. Check cache for existing assignment
        3. Match segments for percentage override
        4. Compute sticky assignment
        5. Record audit and metrics

        Args:
            flag_key: Feature flag key.
            target_id: Target identifier.
            attributes: Target attributes.
            policy: Optional override policy.
            use_cache: Whether to use assignment cache.

        Returns:
            RolloutAssignment with the decision.
        """
        start = time.perf_counter()
        self._evaluation_count += 1

        # Resolve policy
        effective_policy = policy or self._resolve_policy(flag_key)

        if not effective_policy.enabled:
            assignment = RolloutAssignment(
                flag_key=flag_key,
                target_id=target_id,
                assigned=False,
                percentage=0.0,
                duration_ms=(time.perf_counter() - start) * 1000,
                version="disabled",
            )
            self._metrics.record_rollout_eval(
                flag_key, 0.0, False, assignment.duration_ms,
            )
            return assignment

        # Check progressive rollout
        progressive = self._progressive_rollouts.get(flag_key)
        if progressive and progressive.is_active:
            progressive_percentage = progressive.current_percentage
            effective_policy = RolloutPolicy(
                percentage=progressive_percentage,
                hash_key=effective_policy.hash_key,
                enabled=effective_policy.enabled,
                algorithm=effective_policy.algorithm,
                max_buckets=effective_policy.max_buckets,
                sticky=effective_policy.sticky,
                description=f"progressive:{progressive.current_stage_index}",
            )

        # Check cache
        cache_key = f"{flag_key}:{target_id}:{effective_policy.percentage}"
        if use_cache:
            cached = await self._cache.get_assignment(cache_key)
            if cached:
                self._metrics.record_cache_hit(flag_key)
                cached.duration_ms = (time.perf_counter() - start) * 1000
                return cached
            self._metrics.record_cache_miss(flag_key)

        try:
            # Use strategy for evaluation
            strategy = self._get_or_create_strategy(flag_key, effective_policy)
            assignment = await strategy.evaluate(
                flag_key=flag_key,
                target_id=target_id,
                attributes=attributes,
            )

            # Record metrics
            self._metrics.record_rollout_eval(
                flag_key,
                effective_policy.percentage,
                assignment.assigned,
                assignment.duration_ms,
            )

            # Record audit
            await self._audit.record_assignment(
                flag_key=flag_key,
                target_id=target_id,
                assigned=assignment.assigned,
                percentage=assignment.percentage,
                hash_value=assignment.hash_value,
                bucket=assignment.bucket,
                segment_id=assignment.version,
            )

            # Cache result
            if use_cache:
                await self._cache.set_assignment(cache_key, assignment)

            return assignment

        except Exception as e:
            self._error_count += 1
            assignment = RolloutAssignment(
                flag_key=flag_key,
                target_id=target_id,
                assigned=False,
                percentage=effective_policy.percentage,
                duration_ms=(time.perf_counter() - start) * 1000,
                version=f"error:{e}",
            )
            self._metrics.record_rollout_eval(
                flag_key, effective_policy.percentage, False,
            )
            return assignment

    async def evaluate_batch(
        self,
        flag_key: str,
        target_ids: List[str],
        attributes: Optional[Dict[str, Any]] = None,
        policy: Optional[RolloutPolicy] = None,
    ) -> List[RolloutAssignment]:
        """Evaluate rollout for multiple targets."""
        return [
            await self.evaluate(flag_key, tid, attributes, policy)
            for tid in target_ids
        ]

    def set_policy(
        self,
        flag_key: str,
        policy: RolloutPolicy,
    ) -> None:
        """
        Set rollout policy for a feature flag.

        Args:
            flag_key: Feature flag key.
            policy: Rollout policy.
        """
        self._policies[flag_key] = policy
        self._strategies[flag_key] = RolloutStrategy(policy)

    def get_policy(self, flag_key: str) -> Optional[RolloutPolicy]:
        """Get the rollout policy for a flag."""
        return self._policies.get(flag_key)

    def configure_progressive(
        self,
        flag_key: str,
        stages: Optional[List] = None,
    ) -> ProgressiveRollout:
        """
        Configure a progressive rollout for a flag.

        Args:
            flag_key: Feature flag key.
            stages: Optional custom stages.

        Returns:
            ProgressiveRollout instance.
        """
        rollout = ProgressiveRollout(flag_key, stages)
        self._progressive_rollouts[flag_key] = rollout
        return rollout

    def get_progressive(self, flag_key: str) -> Optional[ProgressiveRollout]:
        """Get progressive rollout for a flag."""
        return self._progressive_rollouts.get(flag_key)

    def resolve_policy_percentage(
        self,
        flag_key: str,
        target_id: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        Resolve the effective percentage for a target.

        Accounts for segment overrides and progressive
        rollout stages.

        Args:
            flag_key: Feature flag key.
            target_id: Target identifier.
            attributes: Target attributes.

        Returns:
            Effective percentage.
        """
        policy = self._resolve_policy(flag_key)
        percentage = policy.percentage

        # Check progressive
        progressive = self._progressive_rollouts.get(flag_key)
        if progressive and progressive.is_active:
            percentage = progressive.current_percentage

        # Check segments
        attrs = attributes or {}
        segment = self._segment_engine.resolve(attrs)
        if segment and segment.percentage is not None:
            percentage = segment.percentage

        return percentage

    def add_segment(self, segment) -> None:
        """Add a segment definition to the segment engine."""
        self._segment_engine.add_segment(segment)

    @property
    def segment_engine(self) -> SegmentEngine:
        """Access the segment engine."""
        return self._segment_engine

    @property
    def cache(self) -> RolloutCache:
        """Access the rollout cache."""
        return self._cache

    @property
    def metrics(self) -> RolloutMetrics:
        """Access the rollout metrics."""
        return self._metrics

    @property
    def audit(self) -> RolloutAudit:
        """Access the rollout audit."""
        return self._audit

    def validate_policy(self, policy: RolloutPolicy) -> List[str]:
        """Validate a rollout policy."""
        return self._validator.validate_policy(policy)

    def _resolve_policy(self, flag_key: str) -> RolloutPolicy:
        """Resolve the policy for a flag."""
        return self._policies.get(flag_key, RolloutPolicy())

    def _get_or_create_strategy(
        self,
        flag_key: str,
        policy: RolloutPolicy,
    ) -> RolloutStrategy:
        """Get or create a rollout strategy."""
        if flag_key not in self._strategies:
            strategy = RolloutStrategy(policy)
            # Copy segments
            for segment in self._segment_engine.get_segments():
                strategy.segment_engine.add_segment(segment)
            self._strategies[flag_key] = strategy
        return self._strategies[flag_key]

    def get_stats(self) -> Dict[str, Any]:
        """Get rollout engine statistics."""
        total = self._evaluation_count
        return {
            "evaluations": self._evaluation_count,
            "errors": self._error_count,
            "strategies": len(self._strategies),
            "progressive_rollouts": {
                k: v.get_stats()
                for k, v in self._progressive_rollouts.items()
            },
            "metrics": self._metrics.snapshot(),
            "cache": self._cache.get_stats(),
            "segment": self._segment_engine.get_stats(),
        }

    def reset_stats(self) -> None:
        """Reset all rollout statistics."""
        self._evaluation_count = 0
        self._error_count = 0
        self._metrics.reset()
        self._cache.clear()
        for rollout in self._progressive_rollouts.values():
            rollout.reset()
