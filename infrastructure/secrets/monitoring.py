"""
Secrets monitoring with Prometheus.

Provides extended Prometheus metrics for
the secrets management platform, tracking
provider status, cache hit ratios, rotation
activity, vault latency, and recovery events.
Integrates with the existing SecretsMetrics
and adds supplementary monitoring dimensions.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Gauge, Histogram, generate_latest
    _HAS_PROMETHEUS = True
except ImportError:
    _HAS_PROMETHEUS = False


class SecretsMonitoring:
    """
    Extended secrets monitoring with Prometheus.

    Provides additional metrics beyond the
    base SecretsMetrics, focusing on provider
    health, cache efficiency, rotation status,
    and vault-level performance tracking.

    Metrics:
        icyquant_secrets_active_provider
        icyquant_secrets_provider_failure_total
        icyquant_secrets_recovery_total
        icyquant_secrets_rotation_active
        icyquant_secrets_vault_latency_seconds
        icyquant_secrets_cache_hit_ratio

    Usage:
        monitoring = SecretsMonitoring()
        monitoring.set_provider_active("vault", True)
        monitoring.record_provider_failure("vault", "connection_timeout")
        lines = monitoring.generate_prometheus()
    """

    METRICS_PREFIX = "icyquant_secrets_"

    def __init__(
        self,
        enabled: bool = True,
    ) -> None:
        """
        Initialize secrets monitoring.

        Args:
            enabled: Whether monitoring is enabled.
        """
        self._enabled = enabled
        self._lock = threading.RLock()

        # Provider status tracking
        self._provider_status: Dict[str, bool] = {}
        self._provider_details: Dict[str, Dict[str, Any]] = {}

        # Cache tracking
        self._cache_hits: int = 0
        self._cache_misses: int = 0

        # In-memory counters and gauges
        self._counters: Dict[str, Dict[str, float]] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}

        # Prometheus metrics
        self._prom_counters: Dict[str, Any] = {}
        self._prom_gauges: Dict[str, Any] = {}
        self._prom_histograms: Dict[str, Any] = {}

        if enabled and _HAS_PROMETHEUS:
            self._init_prometheus_metrics()

    def _init_prometheus_metrics(self) -> None:
        """Initialize Prometheus metrics."""
        try:
            self._prom_gauges["active_provider"] = Gauge(
                f"{self.METRICS_PREFIX}active_provider",
                "Whether a provider is active (1=active, 0=inactive)",
                ["provider"],
            )
            self._prom_counters["provider_failure_total"] = Counter(
                f"{self.METRICS_PREFIX}provider_failure_total",
                "Total provider failures",
                ["provider", "reason"],
            )
            self._prom_counters["recovery_total"] = Counter(
                f"{self.METRICS_PREFIX}recovery_total",
                "Total recovery events",
                ["provider", "type"],
            )
            self._prom_gauges["rotation_active"] = Gauge(
                f"{self.METRICS_PREFIX}rotation_active",
                "Number of active rotation operations",
                ["provider"],
            )
            self._prom_histograms["vault_latency"] = Histogram(
                f"{self.METRICS_PREFIX}vault_latency_seconds",
                "Vault operation latency in seconds",
                ["operation", "provider"],
            )
            self._prom_gauges["cache_hit_ratio"] = Gauge(
                f"{self.METRICS_PREFIX}cache_hit_ratio",
                "Cache hit ratio (hits / (hits + misses))",
                ["provider"],
            )
        except Exception:
            self._prom_counters.clear()
            self._prom_gauges.clear()
            self._prom_histograms.clear()

    # ── Provider Status ──

    def set_provider_active(
        self,
        provider: str,
        active: bool = True,
        **details: Any,
    ) -> None:
        """
        Set the active status of a provider.

        Args:
            provider: Provider name.
            active: Whether the provider is active.
            **details: Additional provider details.
        """
        if not self._enabled:
            return

        with self._lock:
            self._provider_status[provider] = active
            if details:
                self._provider_details[provider] = details

        if _HAS_PROMETHEUS and "active_provider" in self._prom_gauges:
            self._prom_gauges["active_provider"].labels(
                provider=provider
            ).set(1 if active else 0)

    def is_provider_active(self, provider: str) -> bool:
        """
        Check if a provider is currently active.

        Args:
            provider: Provider name.

        Returns:
            True if active.
        """
        with self._lock:
            return self._provider_status.get(provider, False)

    def get_provider_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all providers.

        Returns:
            Provider status dictionary.
        """
        with self._lock:
            result: Dict[str, Dict[str, Any]] = {}
            for provider, active in self._provider_status.items():
                result[provider] = {
                    "active": active,
                    "details": self._provider_details.get(
                        provider, {}
                    ),
                }
            return result

    def record_provider_failure(
        self,
        provider: str,
        reason: str = "unknown",
    ) -> None:
        """
        Record a provider failure event.

        Args:
            provider: Provider name.
            reason: Failure reason.
        """
        if not self._enabled:
            return

        with self._lock:
            key = "provider_failure_total"
            self._counters.setdefault(key, {})
            label = f"{provider}/{reason}"
            self._counters[key][label] = (
                self._counters[key].get(label, 0) + 1
            )

        if _HAS_PROMETHEUS and "provider_failure_total" in self._prom_counters:
            self._prom_counters["provider_failure_total"].labels(
                provider=provider, reason=reason
            ).inc()

    def record_recovery(
        self,
        provider: str,
        recovery_type: str = "failover",
    ) -> None:
        """
        Record a recovery event.

        Args:
            provider: Provider name.
            recovery_type: Type of recovery.
        """
        if not self._enabled:
            return

        with self._lock:
            key = "recovery_total"
            self._counters.setdefault(key, {})
            label = f"{provider}/{recovery_type}"
            self._counters[key][label] = (
                self._counters[key].get(label, 0) + 1
            )

        if _HAS_PROMETHEUS and "recovery_total" in self._prom_counters:
            self._prom_counters["recovery_total"].labels(
                provider=provider, type=recovery_type
            ).inc()

    # ── Rotation Tracking ──

    def set_rotation_active(
        self,
        provider: str,
        count: int,
    ) -> None:
        """
        Set the number of active rotation operations.

        Args:
            provider: Provider name.
            count: Number of active rotations.
        """
        if not self._enabled:
            return

        self._gauges[f"rotation_active/{provider}"] = count

        if _HAS_PROMETHEUS and "rotation_active" in self._prom_gauges:
            self._prom_gauges["rotation_active"].labels(
                provider=provider
            ).set(count)

    # ── Vault Latency ──

    def record_vault_latency(
        self,
        operation: str = "read",
        provider: str = "vault",
        latency: float = 0.0,
    ) -> None:
        """
        Record vault operation latency.

        Args:
            operation: Operation type.
            provider: Provider name.
            latency: Latency in seconds.
        """
        if not self._enabled:
            return

        key = f"vault_latency/{operation}/{provider}"
        with self._lock:
            if key not in self._histograms:
                self._histograms[key] = []
            self._histograms[key].append(latency)

        if _HAS_PROMETHEUS and "vault_latency" in self._prom_histograms:
            self._prom_histograms["vault_latency"].labels(
                operation=operation, provider=provider
            ).observe(latency)

    # ── Cache Tracking ──

    def record_cache_hit(
        self,
        provider: str = "local",
    ) -> None:
        """
        Record a cache hit event.

        Args:
            provider: Provider name.
        """
        if not self._enabled:
            return

        with self._lock:
            self._cache_hits += 1
            self._update_cache_hit_ratio(provider)

    def record_cache_miss(
        self,
        provider: str = "local",
    ) -> None:
        """
        Record a cache miss event.

        Args:
            provider: Provider name.
        """
        if not self._enabled:
            return

        with self._lock:
            self._cache_misses += 1
            self._update_cache_hit_ratio(provider)

    def _update_cache_hit_ratio(self, provider: str) -> None:
        """Update the cache hit ratio gauge."""
        total = self._cache_hits + self._cache_misses
        ratio = self._cache_hits / total if total > 0 else 0.0
        self._gauges[f"cache_hit_ratio/{provider}"] = ratio

        if _HAS_PROMETHEUS and "cache_hit_ratio" in self._prom_gauges:
            self._prom_gauges["cache_hit_ratio"].labels(
                provider=provider
            ).set(ratio)

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache hit/miss statistics.

        Returns:
            Cache statistics dictionary.
        """
        with self._lock:
            total = self._cache_hits + self._cache_misses
            ratio = (
                self._cache_hits / total if total > 0 else 0.0
            )
            return {
                "hits": self._cache_hits,
                "misses": self._cache_misses,
                "total": total,
                "hit_ratio": round(ratio, 4),
            }

    # ── Provider Failures ──

    def get_provider_failures(self) -> Dict[str, int]:
        """
        Get provider failure counts.

        Returns:
            Failure counts by provider/reason.
        """
        with self._lock:
            return dict(
                self._counters.get("provider_failure_total", {})
            )

    def get_recoveries(self) -> Dict[str, int]:
        """
        Get recovery event counts.

        Returns:
            Recovery counts by provider/type.
        """
        with self._lock:
            return dict(self._counters.get("recovery_total", {}))

    # ── Export ──

    def generate_prometheus(self) -> str:
        """
        Generate Prometheus text format metrics.

        Returns:
            Prometheus text format string.
        """
        if _HAS_PROMETHEUS:
            try:
                result = generate_latest()
                if isinstance(result, bytes):
                    result = result.decode("utf-8")
                return result
            except Exception:
                pass

        lines: List[str] = []

        # Counters
        for name, labels in self._counters.items():
            lines.append(
                f"# HELP {self.METRICS_PREFIX}{name} Total {name}"
            )
            lines.append(
                f"# TYPE {self.METRICS_PREFIX}{name} counter"
            )
            for label, value in labels.items():
                parts = (
                    label.split("/", 1)
                    if "/" in label
                    else (label, "")
                )
                lines.append(
                    f'{self.METRICS_PREFIX}{name}'
                    f'{{provider="{parts[0]}",reason="{parts[1]}"}}'
                    f" {value}"
                )

        # Gauges
        for name, value in self._gauges.items():
            if "/" in name:
                metric_name, label_val = name.split("/", 1)
            else:
                metric_name, label_val = name, ""
            lines.append(
                f"# HELP {self.METRICS_PREFIX}{metric_name}"
            )
            lines.append(
                f"# TYPE {self.METRICS_PREFIX}{metric_name} gauge"
            )
            if label_val:
                lines.append(
                    f'{self.METRICS_PREFIX}{metric_name}'
                    f'{{provider="{label_val}"}} {value}'
                )
            else:
                lines.append(
                    f"{self.METRICS_PREFIX}{metric_name} {value}"
                )

        # Histograms
        for name, values in self._histograms.items():
            count = len(values)
            avg = sum(values) / count if count > 0 else 0
            if "/" in name:
                metric_name, label_val = name.split("/", 1)
            else:
                metric_name, label_val = name, ""
            lines.append(
                f"# HELP {self.METRICS_PREFIX}{metric_name}"
            )
            lines.append(
                f"# TYPE {self.METRICS_PREFIX}{metric_name} histogram"
            )
            lines.append(
                f'{self.METRICS_PREFIX}{metric_name}_count'
                f'{{operation="{label_val}"}} {count}'
            )
            lines.append(
                f'{self.METRICS_PREFIX}{metric_name}_sum'
                f'{{operation="{label_val}"}} {sum(values)}'
            )

        return "\n".join(lines) + "\n"

    # ── Status & Stats ──

    def get_status(self) -> Dict[str, Any]:
        """
        Get the monitoring status summary.

        Returns:
            Status dictionary.
        """
        with self._lock:
            active_count = sum(
                1 for v in self._provider_status.values() if v
            )
            return {
                "enabled": self._enabled,
                "active_providers": active_count,
                "total_providers": len(self._provider_status),
                "providers": self.get_provider_status(),
                "cache": self.get_cache_stats(),
                "has_prometheus": _HAS_PROMETHEUS,
            }

    def get_stats(self) -> Dict[str, Any]:
        """
        Get monitoring statistics.

        Returns:
            Statistics dictionary with provider
            status, cache stats, failures, recoveries,
            and histogram summaries.
        """
        with self._lock:
            histogram_stats: Dict[str, Dict[str, float]] = {}
            for name, values in self._histograms.items():
                count = len(values)
                histogram_stats[name] = {
                    "count": count,
                    "avg": sum(values) / count if count > 0 else 0,
                    "min": min(values) if values else 0,
                    "max": max(values) if values else 0,
                }

            return {
                "enabled": self._enabled,
                "providers": self.get_provider_status(),
                "cache": self.get_cache_stats(),
                "provider_failures": self.get_provider_failures(),
                "recoveries": self.get_recoveries(),
                "rotation_active": {
                    k.replace("rotation_active/", ""): v
                    for k, v in self._gauges.items()
                    if k.startswith("rotation_active/")
                },
                "histograms": histogram_stats,
                "has_prometheus": _HAS_PROMETHEUS,
            }