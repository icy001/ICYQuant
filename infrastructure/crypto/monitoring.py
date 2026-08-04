"""
Crypto monitoring.

Provides Prometheus-compatible monitoring
for the crypto security platform, tracking
provider status, recovery events, key cache
efficiency, and vault latency.

Metrics:
    icyquant_security_active_provider
    icyquant_security_provider_failure_total
    icyquant_security_recovery_total
    icyquant_security_rotation_active
    icyquant_security_vault_latency_seconds
    icyquant_security_key_cache_hit_ratio

Usage:
    monitoring = CryptoMonitoring()

    tracking a provider failure
    monitoring.record_provider_failure(
        provider="vault",
        reason="connection_timeout",
    )

    tracking recovery
    monitoring.record_recovery(
        provider="vault",
        strategy="failover",
    )

    key cache tracking
    monitoring.record_cache_hit()
    monitoring.record_cache_miss()

    # Export Prometheus metrics
    output = monitoring.generate_prometheus()
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

from .metrics import CryptoMetrics

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Gauge, Histogram, generate_latest
    _HAS_PROMETHEUS = True
except ImportError:
    _HAS_PROMETHEUS = False

_METRICS_PREFIX = "icyquant_security_"


class CryptoMonitoring:
    """
    Crypto monitoring with Prometheus metrics.

    Extends CryptoMetrics with additional
    security-focused metrics for tracking
    provider health, recovery events, key
    rotation status, vault latency, and
    key cache efficiency.

    Features:
    - Provider status tracking
    - Recovery event tracking
    - Key cache hit/miss tracking
    - Vault latency histograms
    - Prometheus text format export
    - Thread-safe with RLock

    Usage:
        monitoring = CryptoMonitoring()

        monitoring.set_active_provider("vault")
        monitoring.record_provider_failure(
            "vault", "connection_timeout"
        )
        monitoring.record_recovery(
            "vault", "failover"
        )
        monitoring.record_cache_hit()
        monitoring.record_cache_miss()

        stats = monitoring.get_stats()
        status = monitoring.get_status()
    """

    def __init__(
        self,
        metrics: Optional[CryptoMetrics] = None,
        enabled: bool = True,
    ) -> None:
        """
        Initialize monitoring.

        Args:
            metrics: CryptoMetrics instance.
            enabled: Whether monitoring is enabled.
        """
        self._metrics = metrics or CryptoMetrics()
        self._enabled = enabled
        self._lock = threading.RLock()

        self._active_provider: str = ""
        self._rotation_active: bool = False

        self._cache_hits: int = 0
        self._cache_misses: int = 0

        self._provider_status: Dict[str, str] = {}
        self._recovery_history: List[Dict[str, Any]] = []
        self._max_recovery_history: int = 500

        self._vault_latencies: List[float] = []
        self._max_vault_latencies: int = 1000

        self._prom_counters: Dict[str, Any] = {}
        self._prom_gauges: Dict[str, Any] = {}
        self._prom_histograms: Dict[str, Any] = {}

        if enabled and _HAS_PROMETHEUS:
            self._init_prometheus()

    def _init_prometheus(self) -> None:
        """Initialize Prometheus metrics."""
        try:
            self._prom_gauges[
                "active_provider"
            ] = Gauge(
                f"{_METRICS_PREFIX}active_provider",
                "Active crypto provider",
                ["provider"],
            )
            self._prom_counters[
                "provider_failure_total"
            ] = Counter(
                f"{_METRICS_PREFIX}provider_failure_total",
                "Total provider failures",
                ["provider", "reason"],
            )
            self._prom_counters[
                "recovery_total"
            ] = Counter(
                f"{_METRICS_PREFIX}recovery_total",
                "Total recovery events",
                ["provider", "strategy"],
            )
            self._prom_gauges[
                "rotation_active"
            ] = Gauge(
                f"{_METRICS_PREFIX}rotation_active",
                "Whether key rotation is active",
            )
            self._prom_histograms[
                "vault_latency"
            ] = Histogram(
                f"{_METRICS_PREFIX}vault_latency_seconds",
                "Vault operation latency in seconds",
                ["operation"],
            )
            self._prom_gauges[
                "key_cache_hit_ratio"
            ] = Gauge(
                f"{_METRICS_PREFIX}key_cache_hit_ratio",
                "Key cache hit ratio",
            )
        except Exception:
            self._prom_counters.clear()
            self._prom_gauges.clear()
            self._prom_histograms.clear()

    # ── Provider Status ──

    def set_active_provider(
        self,
        provider: str,
    ) -> None:
        """
        Set the active crypto provider.

        Args:
            provider: Provider name.
        """
        with self._lock:
            self._active_provider = provider
            self._provider_status[provider] = "active"

        if _HAS_PROMETHEUS and (
            "active_provider" in self._prom_gauges
        ):
            try:
                self._prom_gauges[
                    "active_provider"
                ].labels(provider=provider).set(1)
            except Exception:
                pass

    def set_provider_status(
        self,
        provider: str,
        status: str,
    ) -> None:
        """
        Set a provider's status.

        Args:
            provider: Provider name.
            status: Status string
                (active, degraded, failed).
        """
        with self._lock:
            self._provider_status[provider] = status

    def get_provider_status(
        self,
    ) -> Dict[str, str]:
        """
        Get all provider statuses.

        Returns:
            Provider name to status mapping.
        """
        with self._lock:
            return dict(self._provider_status)

    # ── Provider Failure Tracking ──

    def record_provider_failure(
        self,
        provider: str,
        reason: str = "unknown",
    ) -> None:
        """
        Record a provider failure.

        Args:
            provider: Provider that failed.
            reason: Failure reason.
        """
        if not self._enabled:
            return

        with self._lock:
            self._provider_status[provider] = "failed"

        if _HAS_PROMETHEUS and (
            "provider_failure_total" in self._prom_counters
        ):
            try:
                self._prom_counters[
                    "provider_failure_total"
                ].labels(
                    provider=provider,
                    reason=reason,
                ).inc()
            except Exception:
                pass

    # ── Recovery Event Tracking ──

    def record_recovery(
        self,
        provider: str,
        strategy: str = "failover",
        success: bool = True,
        duration_ms: float = 0.0,
    ) -> None:
        """
        Record a recovery event.

        Args:
            provider: Provider recovered.
            strategy: Recovery strategy used.
            success: Whether recovery succeeded.
            duration_ms: Recovery duration.
        """
        if not self._enabled:
            return

        with self._lock:
            self._provider_status[provider] = (
                "active" if success else "failed"
            )

            record: Dict[str, Any] = {
                "provider": provider,
                "strategy": strategy,
                "success": success,
                "duration_ms": duration_ms,
                "timestamp": time.time(),
            }
            self._recovery_history.append(record)
            if len(self._recovery_history) > (
                self._max_recovery_history
            ):
                self._recovery_history.pop(0)

        if _HAS_PROMETHEUS and (
            "recovery_total" in self._prom_counters
        ):
            try:
                self._prom_counters[
                    "recovery_total"
                ].labels(
                    provider=provider,
                    strategy=strategy,
                ).inc()
            except Exception:
                pass

    def get_recovery_history(
        self,
        provider: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get recovery event history.

        Args:
            provider: Filter by provider.
            limit: Maximum entries.

        Returns:
            List of recovery event records.
        """
        with self._lock:
            history = list(
                reversed(self._recovery_history)
            )
            if provider:
                history = [
                    h
                    for h in history
                    if h["provider"] == provider
                ]
            return history[:limit]

    # ── Rotation Status ──

    def set_rotation_active(
        self,
        active: bool,
    ) -> None:
        """
        Set key rotation active status.

        Args:
            active: Whether rotation is active.
        """
        with self._lock:
            self._rotation_active = active

        if _HAS_PROMETHEUS and (
            "rotation_active" in self._prom_gauges
        ):
            try:
                self._prom_gauges[
                    "rotation_active"
                ].set(1 if active else 0)
            except Exception:
                pass

    # ── Vault Latency Tracking ──

    def record_vault_latency(
        self,
        operation: str = "get_key",
        duration_ms: float = 0.0,
    ) -> None:
        """
        Record a vault operation latency.

        Args:
            operation: Vault operation name.
            duration_ms: Latency in milliseconds.
        """
        if not self._enabled:
            return

        duration_s = duration_ms / 1000.0

        with self._lock:
            self._vault_latencies.append(duration_s)
            if len(self._vault_latencies) > (
                self._max_vault_latencies
            ):
                self._vault_latencies.pop(0)

        if _HAS_PROMETHEUS and (
            "vault_latency" in self._prom_histograms
        ):
            try:
                self._prom_histograms[
                    "vault_latency"
                ].labels(
                    operation=operation,
                ).observe(duration_s)
            except Exception:
                pass

    # ── Key Cache Tracking ──

    def record_cache_hit(
        self,
    ) -> None:
        """Record a key cache hit."""
        if not self._enabled:
            return

        with self._lock:
            self._cache_hits += 1
            self._update_cache_hit_ratio()

    def record_cache_miss(
        self,
    ) -> None:
        """Record a key cache miss."""
        if not self._enabled:
            return

        with self._lock:
            self._cache_misses += 1
            self._update_cache_hit_ratio()

    def _update_cache_hit_ratio(
        self,
    ) -> None:
        """Update the key cache hit ratio gauge."""
        total = self._cache_hits + self._cache_misses
        ratio = (
            self._cache_hits / total
            if total > 0
            else 0.0
        )

        if _HAS_PROMETHEUS and (
            "key_cache_hit_ratio" in self._prom_gauges
        ):
            try:
                self._prom_gauges[
                    "key_cache_hit_ratio"
                ].set(ratio)
            except Exception:
                pass

    def get_cache_stats(
        self,
    ) -> Dict[str, Any]:
        """
        Get key cache statistics.

        Returns:
            Cache hit/miss counts and ratio.
        """
        with self._lock:
            total = self._cache_hits + self._cache_misses
            return {
                "hits": self._cache_hits,
                "misses": self._cache_misses,
                "total": total,
                "hit_ratio": (
                    self._cache_hits / total
                    if total > 0
                    else 0.0
                ),
            }

    # ── Prometheus Export ──

    def generate_prometheus(
        self,
    ) -> str:
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

        for provider, status in self._provider_status.items():
            lines.append(
                f"# HELP {_METRICS_PREFIX}active_provider "
                f"Active crypto provider"
            )
            lines.append(
                f"# TYPE {_METRICS_PREFIX}active_provider gauge"
            )
            lines.append(
                f'{_METRICS_PREFIX}active_provider{{provider="{provider}"}} '
                f'1 if status == "active" else 0'
            )

        lines.append(
            f"# HELP {_METRICS_PREFIX}rotation_active "
            f"Whether key rotation is active"
        )
        lines.append(
            f"# TYPE {_METRICS_PREFIX}rotation_active gauge"
        )
        lines.append(
            f"{_METRICS_PREFIX}rotation_active "
            f"{1 if self._rotation_active else 0}"
        )

        cache_stats = self.get_cache_stats()
        lines.append(
            f"# HELP {_METRICS_PREFIX}key_cache_hit_ratio "
            f"Key cache hit ratio"
        )
        lines.append(
            f"# TYPE {_METRICS_PREFIX}key_cache_hit_ratio gauge"
        )
        lines.append(
            f"{_METRICS_PREFIX}key_cache_hit_ratio "
            f"{cache_stats['hit_ratio']:.4f}"
        )

        if self._vault_latencies:
            lines.append(
                f"# HELP {_METRICS_PREFIX}vault_latency_seconds "
                f"Vault operation latency in seconds"
            )
            lines.append(
                f"# TYPE {_METRICS_PREFIX}vault_latency_seconds histogram"
            )
            avg = (
                sum(self._vault_latencies)
                / len(self._vault_latencies)
            )
            lines.append(
                f'{_METRICS_PREFIX}vault_latency_seconds_count '
                f"{len(self._vault_latencies)}"
            )
            lines.append(
                f'{_METRICS_PREFIX}vault_latency_seconds_sum '
                f"{sum(self._vault_latencies):.6f}"
            )
            lines.append(
                f'{_METRICS_PREFIX}vault_latency_seconds_avg '
                f"{avg:.6f}"
            )

        return "\n".join(lines) + "\n"

    # ── Status & Stats ──

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """
        Get monitoring status.

        Returns:
            Status dictionary with provider,
            rotation, and cache information.
        """
        with self._lock:
            return {
                "enabled": self._enabled,
                "active_provider": self._active_provider,
                "provider_status": dict(
                    self._provider_status
                ),
                "rotation_active": self._rotation_active,
                "cache": self.get_cache_stats(),
                "has_prometheus": _HAS_PROMETHEUS,
                "prom_gauges": list(
                    self._prom_gauges.keys()
                ),
                "prom_counters": list(
                    self._prom_counters.keys()
                ),
                "prom_histograms": list(
                    self._prom_histograms.keys()
                ),
            }

    def get_stats(
        self,
    ) -> Dict[str, Any]:
        """
        Get monitoring statistics.

        Returns:
            Statistics including recovery
            events, vault latency, and cache
            efficiency.
        """
        with self._lock:
            vault_stats: Dict[str, Any] = {}
            if self._vault_latencies:
                sorted_latencies = sorted(
                    self._vault_latencies
                )
                count = len(sorted_latencies)
                vault_stats = {
                    "count": count,
                    "avg_seconds": (
                        sum(sorted_latencies) / count
                    ),
                    "min_seconds": sorted_latencies[0],
                    "max_seconds": sorted_latencies[-1],
                    "p95_seconds": sorted_latencies[
                        int(count * 0.95)
                    ]
                    if count
                    else 0,
                }

            recovery_count: Dict[str, int] = {}
            for r in self._recovery_history:
                provider = r["provider"]
                recovery_count[provider] = (
                    recovery_count.get(provider, 0) + 1
                )

            return {
                "enabled": self._enabled,
                "active_provider": self._active_provider,
                "provider_status": dict(
                    self._provider_status
                ),
                "rotation_active": self._rotation_active,
                "recovery_total": recovery_count,
                "recovery_history_count": len(
                    self._recovery_history
                ),
                "vault_latency": vault_stats,
                "cache": self.get_cache_stats(),
                "max_recovery_history": (
                    self._max_recovery_history
                ),
                "max_vault_latencies": (
                    self._max_vault_latencies
                ),
            }

    def clear_history(
        self,
    ) -> None:
        """Clear all monitoring history."""
        with self._lock:
            self._recovery_history.clear()
            self._vault_latencies.clear()
            self._cache_hits = 0
            self._cache_misses = 0
            self._provider_status.clear()