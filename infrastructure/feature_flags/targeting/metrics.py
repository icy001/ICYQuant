"""
Targeting rule metrics.

Provides metrics collection for targeting
rule evaluation, including rule evaluation
counts, match rates, cache hits, and
compilation statistics.

Metrics follow ICYQuant conventions
with the 'icyquant_feature_rule_' prefix.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Metric name constants
METRIC_RULE_TOTAL = "icyquant_feature_rule_total"
METRIC_RULE_MATCH_TOTAL = "icyquant_feature_rule_match_total"
METRIC_RULE_CACHE_HIT_TOTAL = "icyquant_feature_rule_cache_hit_total"
METRIC_RULE_COMPILE_TOTAL = "icyquant_feature_rule_compile_total"
METRIC_RULE_EVAL_SECONDS = "icyquant_feature_rule_eval_seconds"


class RuleMetrics:
    """
    Metrics collection for targeting rule evaluation.

    Tracks rule-level metrics including evaluation counts,
    match rates, cache effectiveness, and compilation
    statistics. Provides Prometheus-compatible snapshots
    for monitoring dashboards.

    Usage:
        metrics = RuleMetrics()
        metrics.record_eval("risk-rule-001", True, 1.5)
        metrics.record_cache_hit("risk-rule-001")
        snapshot = metrics.snapshot()
    """

    def __init__(self) -> None:
        self._eval_total: Dict[str, int] = {}
        self._match_total: Dict[str, int] = {}
        self._cache_hits: Dict[str, int] = {}
        self._compile_total: Dict[str, int] = {}
        self._eval_durations: Dict[str, list] = {}
        self._lock = asyncio.Lock()

    def record_eval(
        self,
        rule_id: str,
        matched: bool,
        duration_ms: float = 0.0,
    ) -> None:
        """
        Record a rule evaluation.

        Args:
            rule_id: Rule identifier.
            matched: Whether the rule matched.
            duration_ms: Evaluation duration in milliseconds.
        """
        self._eval_total[rule_id] = self._eval_total.get(rule_id, 0) + 1

        if matched:
            self._match_total[rule_id] = self._match_total.get(rule_id, 0) + 1

        if duration_ms > 0:
            if rule_id not in self._eval_durations:
                self._eval_durations[rule_id] = []
            self._eval_durations[rule_id].append(duration_ms / 1000.0)

    def record_cache_hit(self, rule_id: str) -> None:
        """Record a cache hit for a rule."""
        self._cache_hits[rule_id] = self._cache_hits.get(rule_id, 0) + 1

    def record_compile(self, rule_id: str) -> None:
        """Record a rule compilation."""
        self._compile_total[rule_id] = self._compile_total.get(rule_id, 0) + 1

    def record_cache_miss(self, rule_id: str) -> None:
        """Record a cache miss for a rule (tracked as eval without cache hit)."""
        pass  # Implicitly tracked by eval_total - cache_hits

    def get_rule_metrics(self, rule_id: str) -> Dict[str, Any]:
        """
        Get metrics for a specific rule.

        Args:
            rule_id: Rule identifier.

        Returns:
            Dictionary of rule-level metrics.
        """
        evals = self._eval_total.get(rule_id, 0)
        matches = self._match_total.get(rule_id, 0)
        cache_hits = self._cache_hits.get(rule_id, 0)
        compiles = self._compile_total.get(rule_id, 0)

        durations = self._eval_durations.get(rule_id, [])
        avg_duration = sum(durations) / len(durations) if durations else 0.0

        return {
            "rule_id": rule_id,
            "evaluations": evals,
            "matches": matches,
            "match_rate": (matches / evals) if evals > 0 else 0.0,
            "cache_hits": cache_hits,
            "cache_hit_rate": (cache_hits / evals) if evals > 0 else 0.0,
            "compilations": compiles,
            "avg_eval_seconds": avg_duration,
        }

    def snapshot(self) -> Dict[str, Any]:
        """
        Get a complete metrics snapshot.

        Returns:
            Dictionary of all metrics data.
        """
        all_rule_ids = set(self._eval_total.keys())
        all_rule_ids.update(self._match_total.keys())
        all_rule_ids.update(self._cache_hits.keys())
        all_rule_ids.update(self._compile_total.keys())

        rules_metrics = {
            rid: self.get_rule_metrics(rid)
            for rid in all_rule_ids
        }

        total_evals = sum(self._eval_total.values())
        total_matches = sum(self._match_total.values())
        total_cache_hits = sum(self._cache_hits.values())
        total_compiles = sum(self._compile_total.values())

        all_durations = []
        for durs in self._eval_durations.values():
            all_durations.extend(durs)

        avg_duration = sum(all_durations) / len(all_durations) if all_durations else 0.0

        return {
            "total": {
                "evaluations": total_evals,
                "matches": total_matches,
                "match_rate": (total_matches / total_evals) if total_evals > 0 else 0.0,
                "cache_hits": total_cache_hits,
                "cache_hit_rate": (
                    total_cache_hits / total_evals
                    if total_evals > 0 else 0.0
                ),
                "compilations": total_compiles,
                "avg_eval_seconds": avg_duration,
                "rules_tracked": len(all_rule_ids),
            },
            "rules": rules_metrics,
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self._eval_total.clear()
        self._match_total.clear()
        self._cache_hits.clear()
        self._compile_total.clear()
        self._eval_durations.clear()