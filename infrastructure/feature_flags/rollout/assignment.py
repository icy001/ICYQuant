"""
Sticky assignment engine for rollout.

Ensures that the same target always receives
the same rollout decision across multiple
evaluations, service restarts, and scaled deployments.

Supports multiple hash dimensions:
    - account_id
    - user_id
    - strategy_id
    - portfolio_id
    - tenant_id
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional

from .hasher import ConsistentHasher
from .rollout import RolloutAssignment, RolloutPolicy


class StickyAssignment:
    """
    Sticky assignment for consistent rollout decisions.

    Combines consistent hashing with an in-memory cache
    to ensure the same target always gets the same result
    for a given feature flag and percentage.

    The assignment is based on:
        1. A hash of (flag_key + target_id) to a bucket
        2. Comparison of bucket against percentage threshold
        3. Caching the result for fast repeat lookups

    Usage:
        assignment = StickyAssignment()
        result = await assignment.assign(
            flag_key="new-risk-engine",
            target_id="account_123",
            policy=RolloutPolicy(percentage=10.0),
        )
        # result.assigned == True/False, always same for same inputs
    """

    def __init__(
        self,
        max_cache_size: int = 100000,
    ) -> None:
        """
        Initialize the sticky assignment engine.

        Args:
            max_cache_size: Maximum cached assignments.
        """
        self._hasher = ConsistentHasher(algorithm="murmur3")
        self._cache: Dict[str, RolloutAssignment] = {}
        self._max_cache_size = max_cache_size
        self._lock = asyncio.Lock()
        self._assignment_count = 0
        self._cache_hits = 0
        self._cache_misses = 0

    async def assign(
        self,
        flag_key: str,
        target_id: str,
        policy: RolloutPolicy,
        context_attributes: Optional[Dict[str, Any]] = None,
    ) -> RolloutAssignment:
        """
        Determine the rollout assignment for a target.

        The same target with the same flag and policy
        always produces the same result. Results are
        cached for performance.

        Args:
            flag_key: Feature flag key.
            target_id: Target identifier.
            policy: Rollout policy configuration.
            context_attributes: Additional context attributes
                (used for hash_key resolution).

        Returns:
            RolloutAssignment with the decision.
        """
        start = time.perf_counter()
        self._assignment_count += 1

        # Resolve hash key dimension
        hash_dimension = self._resolve_hash_key(
            flag_key,
            target_id,
            policy,
            context_attributes,
        )

        # Check cache
        cache_key = f"{flag_key}:{hash_dimension}:{policy.percentage}:{policy.algorithm}"
        if policy.sticky and cache_key in self._cache:
            cached = self._cache[cache_key]
            cached.duration_ms = (time.perf_counter() - start) * 1000
            self._cache_hits += 1
            return cached

        self._cache_misses += 1

        # Compute hash and bucket
        hasher = ConsistentHasher(algorithm=policy.algorithm)
        combined_key = f"{flag_key}:{hash_dimension}"
        bucket = hasher.hash_to_bucket(combined_key, policy.max_buckets)
        threshold = int(policy.percentage * policy.max_buckets / 100.0)
        assigned = bucket < threshold

        # Build result
        result = RolloutAssignment(
            flag_key=flag_key,
            target_id=target_id,
            hash_value=hasher.hash(combined_key),
            bucket=bucket,
            percentage=policy.percentage,
            assigned=assigned,
            hash_key=hash_dimension,
            algorithm=policy.algorithm,
            sticky=policy.sticky,
            duration_ms=(time.perf_counter() - start) * 1000,
        )

        # Cache if sticky
        if policy.sticky:
            await self._put_cache(cache_key, result)

        return result

    async def assign_batch(
        self,
        flag_key: str,
        target_ids: list,
        policy: RolloutPolicy,
        context_attributes: Optional[Dict[str, Any]] = None,
    ) -> list:
        """
        Assign rollout decisions for multiple targets.

        Args:
            flag_key: Feature flag key.
            target_ids: List of target identifiers.
            policy: Rollout policy configuration.
            context_attributes: Additional context attributes.

        Returns:
            List of RolloutAssignment results.
        """
        return [
            await self.assign(flag_key, tid, policy, context_attributes)
            for tid in target_ids
        ]

    def _resolve_hash_key(
        self,
        flag_key: str,
        target_id: str,
        policy: RolloutPolicy,
        context_attributes: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Resolve the hash key dimension.

        If policy.hash_key is specified and exists in
        context attributes, use that value. Otherwise
        fall back to the target_id.

        Args:
            flag_key: Feature flag key.
            target_id: Target identifier.
            policy: Rollout policy.
            context_attributes: Context attributes.

        Returns:
            Hash key value.
        """
        if policy.hash_key and context_attributes:
            value = context_attributes.get(policy.hash_key)
            if value is not None:
                return str(value)

        return target_id

    async def _put_cache(
        self,
        key: str,
        value: RolloutAssignment,
    ) -> None:
        """Store an assignment in cache with eviction."""
        async with self._lock:
            self._cache[key] = value
            if len(self._cache) > self._max_cache_size:
                # Evict oldest entries (approximate)
                excess = len(self._cache) - self._max_cache_size
                keys = list(self._cache.keys())
                for k in keys[:excess]:
                    del self._cache[k]

    def get_assignment(
        self,
        flag_key: str,
        target_id: str,
        percentage: float,
        algorithm: str = "murmur3",
    ) -> Optional[RolloutAssignment]:
        """
        Get a cached assignment if available.

        Args:
            flag_key: Feature flag key.
            target_id: Target identifier.
            percentage: Current percentage.
            algorithm: Hash algorithm.

        Returns:
            Cached RolloutAssignment or None.
        """
        cache_key = f"{flag_key}:{target_id}:{percentage}:{algorithm}"
        return self._cache.get(cache_key)

    def invalidate(
        self,
        flag_key: Optional[str] = None,
    ) -> int:
        """
        Invalidate cached assignments.

        Args:
            flag_key: Specific flag to invalidate (None = all).

        Returns:
            Number of invalidated entries.
        """
        if flag_key is None:
            count = len(self._cache)
            self._cache.clear()
            return count

        keys_to_remove = [k for k in self._cache if k.startswith(f"{flag_key}:")]
        for k in keys_to_remove:
            del self._cache[k]
        return len(keys_to_remove)

    def get_stats(self) -> Dict[str, Any]:
        """Get assignment engine statistics."""
        total = self._cache_hits + self._cache_misses
        return {
            "assignments": self._assignment_count,
            "cache_size": len(self._cache),
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": (self._cache_hits / total) if total > 0 else 0.0,
            "max_cache_size": self._max_cache_size,
        }

    def reset_stats(self) -> None:
        """Reset assignment statistics."""
        self._assignment_count = 0
        self._cache_hits = 0
        self._cache_misses = 0
