"""
Experiment traffic allocator.

Assigns users to experiment variants using
consistent hashing for stable, deterministic
allocation with sticky assignment guarantees.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..rollout.hasher import ConsistentHasher
from .experiment import Experiment
from .variant import Variant


class VariantAllocator:
    """
    Allocates targets to experiment variants.

    Uses consistent hashing to ensure the
    same target always receives the same
    variant assignment across evaluations.

    Supports weighted traffic splitting
    across multiple variants.

    Usage:
        allocator = VariantAllocator()
        variant = allocator.assign("exp-1", "user-123", variants)
        # variant.variant_id == "treatment"
        # Same user always gets same variant
    """

    def __init__(self) -> None:
        """Initialize the allocator."""
        self._hasher = ConsistentHasher(algorithm="murmur3")
        self._assignment_cache: Dict[str, str] = {}
        self._allocation_count = 0
        self._cache_hits = 0

    def assign(
        self,
        experiment_id: str,
        target_id: str,
        variants: List[Variant],
    ) -> Variant:
        """
        Assign a target to a variant.

        Uses consistent hashing on (experiment_id + target_id)
        to deterministically map to a variant based on
        the configured weights.

        Args:
            experiment_id: Experiment identifier.
            target_id: Target identifier.
            variants: List of available variants.

        Returns:
            Assigned Variant.

        Raises:
            ValueError: If no variants are provided.
        """
        if not variants:
            raise ValueError("No variants provided for allocation")

        self._allocation_count += 1

        # Check cache
        cache_key = f"{experiment_id}:{target_id}"
        if cache_key in self._assignment_cache:
            cached_id = self._assignment_cache[cache_key]
            for v in variants:
                if v.variant_id == cached_id:
                    self._cache_hits += 1
                    return v

        # Compute hash
        combined = f"{experiment_id}:{target_id}"
        hash_value = self._hasher.hash(combined)

        # Weight-based allocation
        total_weight = sum(v.weight for v in variants)
        if total_weight <= 0:
            return variants[0]

        # Map hash to weighted bucket
        bucket = hash_value % int(total_weight * 100)
        cumulative = 0.0
        for variant in variants:
            cumulative += variant.weight * 100
            if bucket < cumulative:
                # Cache and return
                self._assignment_cache[cache_key] = variant.variant_id
                return variant

        # Fallback to last variant
        return variants[-1]

    def get_assignment(
        self,
        experiment_id: str,
        target_id: str,
    ) -> Optional[str]:
        """
        Get the cached variant assignment.

        Args:
            experiment_id: Experiment identifier.
            target_id: Target identifier.

        Returns:
            Variant ID or None.
        """
        cache_key = f"{experiment_id}:{target_id}"
        return self._assignment_cache.get(cache_key)

    def allocate_batch(
        self,
        experiment_id: str,
        target_ids: List[str],
        variants: List[Variant],
    ) -> Dict[str, Variant]:
        """
        Allocate variants for multiple targets.

        Args:
            experiment_id: Experiment identifier.
            target_ids: List of target identifiers.
            variants: Available variants.

        Returns:
            Dict of target_id -> Variant.
        """
        return {
            tid: self.assign(experiment_id, tid, variants)
            for tid in target_ids
        }

    def invalidate(self, experiment_id: Optional[str] = None) -> int:
        """
        Invalidate cached assignments.

        Args:
            experiment_id: Specific experiment (None = all).

        Returns:
            Number of invalidated entries.
        """
        if experiment_id is None:
            count = len(self._assignment_cache)
            self._assignment_cache.clear()
            return count

        keys_to_remove = [
            k for k in self._assignment_cache
            if k.startswith(f"{experiment_id}:")
        ]
        for k in keys_to_remove:
            del self._assignment_cache[k]
        return len(keys_to_remove)

    def get_variant_distribution(
        self,
        experiment_id: str,
        variants: List[Variant],
        sample_size: int = 1000,
    ) -> Dict[str, int]:
        """
        Estimate variant distribution for a sample.

        Args:
            experiment_id: Experiment identifier.
            variants: Available variants.
            sample_size: Number of sample targets.

        Returns:
            Dict of variant_id -> count.
        """
        distribution: Dict[str, int] = {v.variant_id: 0 for v in variants}
        for i in range(sample_size):
            variant = self.assign(experiment_id, f"_sample_{i}", variants)
            distribution[variant.variant_id] += 1
        return distribution

    def get_stats(self) -> Dict[str, Any]:
        """Get allocator statistics."""
        return {
            "allocations": self._allocation_count,
            "cache_hits": self._cache_hits,
            "cache_size": len(self._assignment_cache),
            "hit_rate": (
                self._cache_hits / self._allocation_count
                if self._allocation_count > 0
                else 0.0
            ),
        }

    def reset_stats(self) -> None:
        """Reset allocator statistics."""
        self._allocation_count = 0
        self._cache_hits = 0
