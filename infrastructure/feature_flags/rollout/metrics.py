"""
Rollout-specific metrics.

Provides Prometheus-compatible metrics
for monitoring rollout operations including
evaluations, assignments, cache performance,
and progressive rollout tracking.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Metric name constants
METRIC_ROLLOUT_EVAL_TOTAL = "icyquant_rollout_eval_total"
METRIC_ROLLOUT_ASSIGNMENT_TOTAL = "icyquant_rollout_assignment_total"
METRIC_ROLLOUT_CACHE_HIT_TOTAL = "icyquant_rollout_cache_hit_total"
METRIC_ROLLOUT_CACHE_MISS_TOTAL = "icyquant_rollout_cache_miss_total"
METRIC_ROLLOUT_PROGRESSIVE_TOTAL = "icyquant_rollout_progressive_total"
METRIC_ROLLOUT_LATENCY_SECONDS = "icyquant_rollout_latency_seconds"
METRIC_ROLLOUT_SEGMENT_MATCH_TOTAL = "icyquant_rollout_segment_match_total"
METRIC_ROLLOUT_HASH_COMPUTE_TOTAL = "icyquant_rollout_hash_compute_total"


class RolloutMetrics:
    """
    Prometheus-compatible metrics for rollout operations.

    Tracks:
        - Total rollout evaluations
        - Assignment decisions (assigned vs not)
        - Cache hit/miss rates
        - Progressive rollout progress
        - Evaluation latency

    Usage:
        metrics = RolloutMetrics()
        metrics.record_rollout_eval("new-risk", 10.0, True, 0.5)
        snapshot = metrics.snapshot()
    """

    def __init__(self) -> None:
        """Initialize rollout metrics."""
        self._eval_total: Dict[str, int] = {}
        self._assignment_total: Dict[str, int] = {}
        self._assigned_total: Dict[str, int] = {}
        self._not_assigned_total: Dict[str, int] = {}
        self._cache_hits: Dict[str, int] = {}
        self._cache_misses: Dict[str, int] = {}
        self._progressive_total: Dict[str, int] = {}
        self._progressive_stage: Dict[str, int] = {}
        self._segment_match_total: Dict[str, int] = {}
        self._hash_compute_total: Dict[str, int] = {}
        self._latency_sum: Dict[str, float] = {}
        self._latency_count: Dict[str, int] = {}
        self._lock = asyncio.Lock()

    def record_rollout_eval(
        self,
        flag_key: str,
        percentage: float,
        assigned: bool,
        duration_ms: float = 0.0,
    ) -> None:
        """
        Record a rollout evaluation.

        Args:
            flag_key: Feature flag key.
            percentage: Rollout percentage used.
            assigned: Whether target was assigned.
            duration_ms: Evaluation duration.
        """
        self._eval_total[flag_key] = self._eval_total.get(flag_key, 0) + 1
        self._assignment_total[flag_key] = (
            self._assignment_total.get(flag_key, 0) + 1
        )

        if assigned:
            self._assigned_total[flag_key] = (
                self._assigned_total.get(flag_key, 0) + 1
            )
        else:
            self._not_assigned_total[flag_key] = (
                self._not_assigned_total.get(flag_key, 0) + 1
            )

        if duration_ms > 0:
            current_sum = self._latency_sum.get(flag_key, 0.0)
            current_count = self._latency_count.get(flag_key, 0)
            self._latency_sum[flag_key] = current_sum + duration_ms
            self._latency_count[flag_key] = current_count + 1

    def record_cache_hit(
        self,
        flag_key: str = "",
    ) -> None:
        """Record a rollout cache hit."""
        self._cache_hits[flag_key] = self._cache_hits.get(flag_key, 0) + 1

    def record_cache_miss(
        self,
        flag_key: str = "",
    ) -> None:
        """Record a rollout cache miss."""
        self._cache_misses[flag_key] = self._cache_misses.get(flag_key, 0) + 1

    def record_progressive_stage(
        self,
        feature_key: str,
        stage_index: int,
        percentage: float,
    ) -> None:
        """
        Record a progressive rollout stage transition.

        Args:
            feature_key: Feature key.
            stage_index: New stage index.
            percentage: New stage percentage.
        """
        key = f"{feature_key}:{stage_index}"
        self._progressive_total[key] = (
            self._progressive_total.get(key, 0) + 1
        )
        self._progressive_stage[feature_key] = stage_index

    def record_segment_match(
        self,
        segment_id: str,
        flag_key: str = "",
    ) -> None:
        """Record a segment match."""
        key = f"{flag_key}:{segment_id}" if flag_key else segment_id
        self._segment_match_total[key] = (
            self._segment_match_total.get(key, 0) + 1
        )

    def record_hash_computation(
        self,
        algorithm: str = "murmur3",
    ) -> None:
        """Record a hash computation."""
        self._hash_compute_total[algorithm] = (
            self._hash_compute_total.get(algorithm, 0) + 1
        )

    def get_eval_total(self, flag_key: str) -> int:
        """Get total rollout evaluations for a flag."""
        return self._eval_total.get(flag_key, 0)

    def get_assignment_rate(self, flag_key: str) -> float:
        """Get assignment rate for a flag."""
        assigned = self._assigned_total.get(flag_key, 0)
        total = self._assignment_total.get(flag_key, 0)
        if total > 0:
            return assigned / total
        return 0.0

    def get_avg_latency(self, flag_key: str) -> float:
        """Get average rollout latency in seconds."""
        count = self._latency_count.get(flag_key, 0)
        if count > 0:
            return self._latency_sum.get(flag_key, 0.0) / count / 1000.0
        return 0.0

    def get_cache_hit_ratio(self, flag_key: str = "") -> float:
        """Get cache hit ratio."""
        hits = self._cache_hits.get(flag_key, 0)
        misses = self._cache_misses.get(flag_key, 0)
        total = hits + misses
        if total > 0:
            return hits / total
        return 0.0

    def snapshot(self) -> Dict[str, Any]:
        """
        Get a full metrics snapshot.

        Returns:
            Dictionary with all metric values.
        """
        return {
            "eval_total": dict(self._eval_total),
            "assignment_total": dict(self._assignment_total),
            "assigned_total": dict(self._assigned_total),
            "not_assigned_total": dict(self._not_assigned_total),
            "assignment_rates": {
                k: self.get_assignment_rate(k)
                for k in self._assignment_total
            },
            "cache_hits": dict(self._cache_hits),
            "cache_misses": dict(self._cache_misses),
            "cache_hit_ratio": self.get_cache_hit_ratio(),
            "progressive_total": dict(self._progressive_total),
            "progressive_stage": dict(self._progressive_stage),
            "segment_match_total": dict(self._segment_match_total),
            "hash_compute_total": dict(self._hash_compute_total),
            "avg_latency_seconds": {
                k: self.get_avg_latency(k)
                for k in self._latency_count
            },
        }

    def get_counter_values(self) -> Dict[str, int]:
        """Get values formatted as Prometheus counters."""
        return {
            METRIC_ROLLOUT_EVAL_TOTAL: sum(self._eval_total.values()),
            METRIC_ROLLOUT_ASSIGNMENT_TOTAL: sum(self._assignment_total.values()),
            METRIC_ROLLOUT_CACHE_HIT_TOTAL: sum(self._cache_hits.values()),
            METRIC_ROLLOUT_CACHE_MISS_TOTAL: sum(self._cache_misses.values()),
            METRIC_ROLLOUT_PROGRESSIVE_TOTAL: sum(self._progressive_total.values()),
            METRIC_ROLLOUT_SEGMENT_MATCH_TOTAL: sum(
                self._segment_match_total.values()
            ),
            METRIC_ROLLOUT_HASH_COMPUTE_TOTAL: sum(
                self._hash_compute_total.values()
            ),
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self._eval_total.clear()
        self._assignment_total.clear()
        self._assigned_total.clear()
        self._not_assigned_total.clear()
        self._cache_hits.clear()
        self._cache_misses.clear()
        self._progressive_total.clear()
        self._progressive_stage.clear()
        self._segment_match_total.clear()
        self._hash_compute_total.clear()
        self._latency_sum.clear()
        self._latency_count.clear()
