"""
Feature flag platform metrics.

Provides Prometheus-compatible metrics for
monitoring feature flag evaluation, cache
performance, and platform health. Follows
the ICYQuant metrics conventions with the
'icyquant_' prefix and standard labels.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Metric name constants following Prometheus conventions
METRIC_EVAL_TOTAL = "icyquant_feature_eval_total"
METRIC_EVAL_DURATION = "icyquant_feature_eval_duration_seconds"
METRIC_ENABLED_TOTAL = "icyquant_feature_enabled_total"
METRIC_DISABLED_TOTAL = "icyquant_feature_disabled_total"
METRIC_CACHE_HIT_TOTAL = "icyquant_feature_cache_hit_total"
METRIC_CACHE_MISS_TOTAL = "icyquant_feature_cache_miss_total"
METRIC_REGISTERED_TOTAL = "icyquant_feature_registered_total"
METRIC_UPDATED_TOTAL = "icyquant_feature_updated_total"
METRIC_DELETED_TOTAL = "icyquant_feature_deleted_total"
METRIC_AUDIT_TOTAL = "icyquant_feature_audit_total"
METRIC_ERROR_TOTAL = "icyquant_feature_error_total"
METRIC_CIRCUIT_BREAKER_TOTAL = "icyquant_feature_circuit_breaker_total"
METRIC_RULE_TOTAL = "icyquant_feature_rule_total"
METRIC_RULE_MATCH_TOTAL = "icyquant_feature_rule_match_total"
METRIC_RULE_CACHE_HIT_TOTAL = "icyquant_feature_rule_cache_hit_total"
METRIC_RULE_COMPILE_TOTAL = "icyquant_feature_rule_compile_total"
METRIC_RULE_EVAL_SECONDS = "icyquant_feature_rule_eval_seconds"

# Standard labels for all metrics
STANDARD_LABELS = ("service", "module", "instance", "environment", "host", "region")


class FeatureFlagMetrics:
    """
    Prometheus-compatible metrics for feature flag platform.

    Collects counters and histograms for monitoring
    feature flag evaluation, cache effectiveness,
    and platform operations.

    Usage:
        metrics = FeatureFlagMetrics(labels={"env": "prod"})
        metrics.record_eval("trading.new_risk", True, "hit", 1.5)
        metrics.record_cache_hit("trading.new_risk")
        snapshot = metrics.snapshot()
    """

    def __init__(
        self,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Initialize feature flag metrics.

        Args:
            labels: Additional labels to attach to all metrics.
        """
        self._labels = labels or {}
        self._eval_total: Dict[str, int] = {}
        self._eval_duration: Dict[str, float] = {}
        self._eval_duration_count: Dict[str, int] = {}
        self._enabled_total: Dict[str, int] = {}
        self._disabled_total: Dict[str, int] = {}
        self._cache_hits: Dict[str, int] = {}
        self._cache_misses: Dict[str, int] = {}
        self._registered_total: int = 0
        self._updated_total: int = 0
        self._deleted_total: int = 0
        self._audit_total: int = 0
        self._error_total: Dict[str, int] = {}
        self._circuit_breaker_total: Dict[str, int] = {}
        self._lock = asyncio.Lock()

    def record_eval(
        self,
        flag_key: str,
        value: Any,
        result: str = "hit",
        duration_ms: float = 0.0,
    ) -> None:
        """
        Record a feature flag evaluation.

        Args:
            flag_key: Feature flag key.
            value: Evaluated value.
            result: Evaluation result (hit, miss, error, no_rule).
            duration_ms: Evaluation duration in milliseconds.
        """
        self._eval_total[flag_key] = self._eval_total.get(flag_key, 0) + 1

        if duration_ms > 0:
            key = flag_key
            current_sum = self._eval_duration.get(key, 0.0)
            current_count = self._eval_duration_count.get(key, 0)
            self._eval_duration[key] = current_sum + duration_ms
            self._eval_duration_count[key] = current_count + 1

        if result == "hit":
            if value is not None and bool(value):
                self._enabled_total[flag_key] = (
                    self._enabled_total.get(flag_key, 0) + 1
                )
            else:
                self._disabled_total[flag_key] = (
                    self._disabled_total.get(flag_key, 0) + 1
                )

    def record_cache_hit(
        self,
        flag_key: str,
    ) -> None:
        """
        Record a cache hit.

        Args:
            flag_key: Feature flag key.
        """
        self._cache_hits[flag_key] = (
            self._cache_hits.get(flag_key, 0) + 1
        )

    def record_cache_miss(
        self,
        flag_key: str,
    ) -> None:
        """
        Record a cache miss.

        Args:
            flag_key: Feature flag key.
        """
        self._cache_misses[flag_key] = (
            self._cache_misses.get(flag_key, 0) + 1
        )

    def record_register(
        self,
        flag_key: str = "",
    ) -> None:
        """
        Record a flag registration.

        Args:
            flag_key: Feature flag key.
        """
        self._registered_total += 1

    def record_update(
        self,
        flag_key: str = "",
    ) -> None:
        """
        Record a flag update.

        Args:
            flag_key: Feature flag key.
        """
        self._updated_total += 1

    def record_delete(
        self,
        flag_key: str = "",
    ) -> None:
        """
        Record a flag deletion.

        Args:
            flag_key: Feature flag key.
        """
        self._deleted_total += 1

    def record_audit(
        self,
        action: str = "",
    ) -> None:
        """
        Record an audit event.

        Args:
            action: Audit action type.
        """
        self._audit_total += 1

    def record_error(
        self,
        flag_key: str,
        error_type: str = "evaluation",
    ) -> None:
        """
        Record a flag evaluation error.

        Args:
            flag_key: Feature flag key.
            error_type: Type of error.
        """
        key = f"{flag_key}:{error_type}"
        self._error_total[key] = self._error_total.get(key, 0) + 1

    def record_circuit_breaker(
        self,
        flag_key: str,
    ) -> None:
        """
        Record a circuit breaker event.

        Args:
            flag_key: Feature flag key.
        """
        self._circuit_breaker_total[flag_key] = (
            self._circuit_breaker_total.get(flag_key, 0) + 1
        )

    def get_eval_total(self, flag_key: str) -> int:
        """Get total evaluations for a flag."""
        return self._eval_total.get(flag_key, 0)

    def get_avg_duration(self, flag_key: str) -> float:
        """Get average evaluation duration in seconds."""
        count = self._eval_duration_count.get(flag_key, 0)
        if count > 0:
            return self._eval_duration.get(flag_key, 0.0) / count / 1000.0
        return 0.0

    def get_cache_hit_ratio(self, flag_key: str) -> float:
        """Get cache hit ratio for a flag."""
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
            "eval_duration_ms_sum": dict(self._eval_duration),
            "eval_duration_count": dict(self._eval_duration_count),
            "avg_duration_seconds": {
                k: self.get_avg_duration(k)
                for k in self._eval_duration_count
            },
            "enabled_total": dict(self._enabled_total),
            "disabled_total": dict(self._disabled_total),
            "cache_hits": dict(self._cache_hits),
            "cache_misses": dict(self._cache_misses),
            "cache_hit_ratios": {
                k: self.get_cache_hit_ratio(k)
                for k in set(list(self._cache_hits.keys()) + list(self._cache_misses.keys()))
            },
            "registered_total": self._registered_total,
            "updated_total": self._updated_total,
            "deleted_total": self._deleted_total,
            "audit_total": self._audit_total,
            "error_total": dict(self._error_total),
            "circuit_breaker_total": dict(self._circuit_breaker_total),
            "labels": dict(self._labels),
        }

    def get_counter_values(self) -> Dict[str, int]:
        """
        Get values formatted as Prometheus counters.

        Returns:
            Dictionary of metric_name -> value mappings.
        """
        return {
            METRIC_EVAL_TOTAL: sum(self._eval_total.values()),
            METRIC_ENABLED_TOTAL: sum(self._enabled_total.values()),
            METRIC_DISABLED_TOTAL: sum(self._disabled_total.values()),
            METRIC_CACHE_HIT_TOTAL: sum(self._cache_hits.values()),
            METRIC_CACHE_MISS_TOTAL: sum(self._cache_misses.values()),
            METRIC_REGISTERED_TOTAL: self._registered_total,
            METRIC_UPDATED_TOTAL: self._updated_total,
            METRIC_DELETED_TOTAL: self._deleted_total,
            METRIC_AUDIT_TOTAL: self._audit_total,
            METRIC_ERROR_TOTAL: sum(self._error_total.values()),
            METRIC_CIRCUIT_BREAKER_TOTAL: sum(
                self._circuit_breaker_total.values()
            ),
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self._eval_total.clear()
        self._eval_duration.clear()
        self._eval_duration_count.clear()
        self._enabled_total.clear()
        self._disabled_total.clear()
        self._cache_hits.clear()
        self._cache_misses.clear()
        self._registered_total = 0
        self._updated_total = 0
        self._deleted_total = 0
        self._audit_total = 0
        self._error_total.clear()
        self._circuit_breaker_total.clear()

    def get_labels(self) -> Dict[str, str]:
        """Get current metric labels."""
        return dict(self._labels)


class FeatureFlagPrometheusExporter:
    """
    Exports feature flag metrics in Prometheus exposition format.

    Converts FeatureFlagMetrics counters and histograms
    into the text-based exposition format used by
    Prometheus for scraping.

    Usage:
        exporter = FeatureFlagPrometheusExporter(metrics)
        output = exporter.export_text()
    """

    def __init__(
        self,
        metrics: FeatureFlagMetrics,
    ) -> None:
        """
        Initialize the exporter.

        Args:
            metrics: FeatureFlagMetrics instance to export.
        """
        self._metrics = metrics

    def export_text(self) -> str:
        """
        Export metrics in Prometheus text exposition format.

        Returns:
            Prometheus text format string.
        """
        lines: list[str] = []
        labels_str = self._format_labels(self._metrics.get_labels())

        counters = self._metrics.get_counter_values()

        for name, value in counters.items():
            lines.append(f"# HELP {name} Total {name.replace('icyquant_feature_', '').replace('_', ' ')}")
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name}{labels_str} {value}")

        snapshot = self._metrics.snapshot()

        # Per-flag breakdowns
        for flag_key, count in snapshot["eval_total"].items():
            flag_label = f'{{flag_key="{flag_key}"{labels_str[1:-1] if labels_str else ""}}}'
            lines.append(
                f'{METRIC_EVAL_TOTAL}{flag_label} {count}'
            )

        for flag_key, avg in snapshot["avg_duration_seconds"].items():
            flag_label = f'{{flag_key="{flag_key}"{labels_str[1:-1] if labels_str else ""}}}'
            lines.append(
                f'{METRIC_EVAL_DURATION}{flag_label} {avg:.6f}'
            )

        for flag_key, count in snapshot["enabled_total"].items():
            flag_label = f'{{flag_key="{flag_key}"{labels_str[1:-1] if labels_str else ""}}}'
            lines.append(
                f'{METRIC_ENABLED_TOTAL}{flag_label} {count}'
            )

        for flag_key, count in snapshot["disabled_total"].items():
            flag_label = f'{{flag_key="{flag_key}"{labels_str[1:-1] if labels_str else ""}}}'
            lines.append(
                f'{METRIC_DISABLED_TOTAL}{flag_label} {count}'
            )

        for flag_key, count in snapshot["cache_hits"].items():
            flag_label = f'{{flag_key="{flag_key}"{labels_str[1:-1] if labels_str else ""}}}'
            lines.append(
                f'{METRIC_CACHE_HIT_TOTAL}{flag_label} {count}'
            )

        for flag_key, count in snapshot["cache_misses"].items():
            flag_label = f'{{flag_key="{flag_key}"{labels_str[1:-1] if labels_str else ""}}}'
            lines.append(
                f'{METRIC_CACHE_MISS_TOTAL}{flag_label} {count}'
            )

        return "\n".join(lines) + "\n"

    def _format_labels(self, labels: Dict[str, str]) -> str:
        """Format labels for Prometheus output."""
        if not labels:
            return ""
        parts = [f'{k}="{v}"' for k, v in sorted(labels.items())]
        return "{" + ",".join(parts) + "}"