"""
Secrets platform metrics.

Provides Prometheus-compatible metrics
for the secrets management platform,
tracking reads, cache operations,
refresh events, and access denials.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, List, Optional

try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        generate_latest,
        REGISTRY,
    )
    _HAS_PROMETHEUS = True
except ImportError:
    _HAS_PROMETHEUS = False


class SecretsMetrics:
    """
    Secrets platform metrics collector.

    Tracks all secret operations with
    Prometheus-compatible counters,
    gauges, and histograms for monitoring
    and alerting.

    Usage:
        metrics = SecretsMetrics()
        metrics.record_read()
        metrics.record_cache_hit()
        lines = metrics.generate_prometheus()
    """

    METRICS_PREFIX = "icyquant_secret_"
    VAULT_METRICS_PREFIX = "icyquant_vault_"

    def __init__(self, enabled: bool = True) -> None:
        """
        Initialize metrics collector.

        Args:
            enabled: Whether metrics collection is enabled.
        """
        self._enabled = enabled
        self._lock = threading.Lock()

        # In-memory counters (always available)
        self._counters: Dict[str, Dict[str, float]] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}

        # Vault-specific in-memory counters
        self._vault_counters: Dict[str, Dict[str, float]] = {}
        self._vault_histograms: Dict[str, List[float]] = {}
        self._vault_gauges: Dict[str, float] = {}

        # Prometheus metrics (if available)
        self._prom_counters: Dict[str, Any] = {}
        self._prom_gauges: Dict[str, Any] = {}
        self._prom_histograms: Dict[str, Any] = {}

        self._vault_prom_counters: Dict[str, Any] = {}
        self._vault_prom_histograms: Dict[str, Any] = {}
        self._vault_prom_gauges: Dict[str, Any] = {}

        if enabled and _HAS_PROMETHEUS:
            self._init_prometheus_metrics()
            self._init_vault_prometheus_metrics()

    def _init_prometheus_metrics(self) -> None:
        """Initialize Prometheus metrics."""
        try:
            self._prom_counters["read_total"] = Counter(
                f"{self.METRICS_PREFIX}read_total",
                "Total secret reads",
                ["provider", "namespace"],
            )
            self._prom_counters["cache_hit_total"] = Counter(
                f"{self.METRICS_PREFIX}cache_hit_total",
                "Total cache hits",
                ["provider", "namespace"],
            )
            self._prom_counters["cache_miss_total"] = Counter(
                f"{self.METRICS_PREFIX}cache_miss_total",
                "Total cache misses",
                ["provider", "namespace"],
            )
            self._prom_counters["refresh_total"] = Counter(
                f"{self.METRICS_PREFIX}refresh_total",
                "Total secret refreshes",
                ["provider", "namespace"],
            )
            self._prom_counters["access_denied_total"] = Counter(
                f"{self.METRICS_PREFIX}access_denied_total",
                "Total access denials",
                ["provider", "role"],
            )
            self._prom_counters["validation_failure_total"] = Counter(
                f"{self.METRICS_PREFIX}validation_failure_total",
                "Total validation failures",
                ["provider", "type"],
            )

            self._prom_gauges["active_secrets"] = Gauge(
                f"{self.METRICS_PREFIX}active_secrets",
                "Number of active secrets",
                ["provider", "namespace"],
            )
            self._prom_gauges["cache_entries"] = Gauge(
                f"{self.METRICS_PREFIX}cache_entries",
                "Number of cached entries",
                ["provider"],
            )

            self._prom_histograms["provider_latency"] = Histogram(
                f"{self.METRICS_PREFIX}provider_latency_seconds",
                "Provider operation latency",
                ["provider", "operation"],
            )
        except Exception:
            self._prom_counters.clear()
            self._prom_gauges.clear()
            self._prom_histograms.clear()

    # ── Recording ──

    def record_read(
        self,
        provider: str = "local",
        namespace: str = "default",
    ) -> None:
        """Record a secret read."""
        if not self._enabled:
            return
        with self._lock:
            key = "read_total"
            self._counters.setdefault(key, {})
            label = f"{provider}/{namespace}"
            self._counters[key][label] = self._counters[key].get(label, 0) + 1

        if _HAS_PROMETHEUS and key in self._prom_counters:
            self._prom_counters[key].labels(
                provider=provider, namespace=namespace
            ).inc()

    def record_cache_hit(
        self,
        provider: str = "local",
        namespace: str = "default",
    ) -> None:
        """Record a cache hit."""
        if not self._enabled:
            return
        with self._lock:
            key = "cache_hit_total"
            self._counters.setdefault(key, {})
            label = f"{provider}/{namespace}"
            self._counters[key][label] = self._counters[key].get(label, 0) + 1

        if _HAS_PROMETHEUS and key in self._prom_counters:
            self._prom_counters[key].labels(
                provider=provider, namespace=namespace
            ).inc()

    def record_cache_miss(
        self,
        provider: str = "local",
        namespace: str = "default",
    ) -> None:
        """Record a cache miss."""
        if not self._enabled:
            return
        with self._lock:
            key = "cache_miss_total"
            self._counters.setdefault(key, {})
            label = f"{provider}/{namespace}"
            self._counters[key][label] = self._counters[key].get(label, 0) + 1

        if _HAS_PROMETHEUS and key in self._prom_counters:
            self._prom_counters[key].labels(
                provider=provider, namespace=namespace
            ).inc()

    def record_refresh(
        self,
        provider: str = "local",
        namespace: str = "default",
    ) -> None:
        """Record a secret refresh."""
        if not self._enabled:
            return
        with self._lock:
            key = "refresh_total"
            self._counters.setdefault(key, {})
            label = f"{provider}/{namespace}"
            self._counters[key][label] = self._counters[key].get(label, 0) + 1

        if _HAS_PROMETHEUS and key in self._prom_counters:
            self._prom_counters[key].labels(
                provider=provider, namespace=namespace
            ).inc()

    def record_access_denied(
        self,
        provider: str = "local",
        role: str = "",
    ) -> None:
        """Record an access denial."""
        if not self._enabled:
            return
        with self._lock:
            key = "access_denied_total"
            self._counters.setdefault(key, {})
            label = f"{provider}/{role}"
            self._counters[key][label] = self._counters[key].get(label, 0) + 1

        if _HAS_PROMETHEUS and key in self._prom_counters:
            self._prom_counters[key].labels(
                provider=provider, role=role
            ).inc()

    def record_validation_failure(
        self,
        provider: str = "local",
        failure_type: str = "",
    ) -> None:
        """Record a validation failure."""
        if not self._enabled:
            return
        with self._lock:
            key = "validation_failure_total"
            self._counters.setdefault(key, {})
            label = f"{provider}/{failure_type}"
            self._counters[key][label] = self._counters[key].get(label, 0) + 1

        if _HAS_PROMETHEUS and key in self._prom_counters:
            self._prom_counters[key].labels(
                provider=provider, type=failure_type
            ).inc()

    def record_provider_latency(
        self,
        provider: str = "local",
        operation: str = "read",
        latency: float = 0.0,
    ) -> None:
        """Record provider operation latency."""
        if not self._enabled:
            return

        key = f"latency_{provider}_{operation}"
        with self._lock:
            if key not in self._histograms:
                self._histograms[key] = []
            self._histograms[key].append(latency)

        if _HAS_PROMETHEUS and "provider_latency" in self._prom_histograms:
            self._prom_histograms["provider_latency"].labels(
                provider=provider, operation=operation
            ).observe(latency)

    def set_active_secrets(
        self,
        count: int,
        provider: str = "local",
        namespace: str = "default",
    ) -> None:
        """Set the active secrets gauge."""
        if not self._enabled:
            return
        self._gauges[f"active_secrets/{provider}/{namespace}"] = count
        if _HAS_PROMETHEUS and "active_secrets" in self._prom_gauges:
            self._prom_gauges["active_secrets"].labels(
                provider=provider, namespace=namespace
            ).set(count)

    def set_cache_entries(
        self,
        count: int,
        provider: str = "local",
    ) -> None:
        """Set the cache entries gauge."""
        if not self._enabled:
            return
        self._gauges[f"cache_entries/{provider}"] = count
        if _HAS_PROMETHEUS and "cache_entries" in self._prom_gauges:
            self._prom_gauges["cache_entries"].labels(
                provider=provider
            ).set(count)

    # ── Vault Prometheus Metrics ──

    def _init_vault_prometheus_metrics(self) -> None:
        """Initialize Vault-specific Prometheus metrics."""
        try:
            self._vault_prom_counters["request_total"] = Counter(
                f"{self.VAULT_METRICS_PREFIX}request_total",
                "Total Vault requests",
                ["operation", "path"],
            )
            self._vault_prom_counters["auth_success_total"] = Counter(
                f"{self.VAULT_METRICS_PREFIX}auth_success_total",
                "Total Vault authentication successes",
                ["method"],
            )
            self._vault_prom_counters["auth_failure_total"] = Counter(
                f"{self.VAULT_METRICS_PREFIX}auth_failure_total",
                "Total Vault authentication failures",
                ["method", "reason"],
            )
            self._vault_prom_counters["lease_renew_total"] = Counter(
                f"{self.VAULT_METRICS_PREFIX}lease_renew_total",
                "Total Vault lease renewals",
                ["status"],
            )
            self._vault_prom_counters["failover_total"] = Counter(
                f"{self.VAULT_METRICS_PREFIX}failover_total",
                "Total Vault failover events",
                ["reason"],
            )

            self._vault_prom_histograms["request_latency"] = Histogram(
                f"{self.VAULT_METRICS_PREFIX}request_latency_seconds",
                "Vault request latency",
                ["operation"],
            )

            self._vault_prom_gauges["active_leases"] = Gauge(
                f"{self.VAULT_METRICS_PREFIX}active_leases",
                "Number of active Vault leases",
            )
            self._vault_prom_gauges["circuit_state"] = Gauge(
                f"{self.VAULT_METRICS_PREFIX}circuit_state",
                "Vault circuit breaker state (0=closed, 1=open, 2=half-open)",
            )
        except Exception:
            self._vault_prom_counters.clear()
            self._vault_prom_histograms.clear()
            self._vault_prom_gauges.clear()

    # ── Vault Recording ──

    def record_vault_request(
        self,
        operation: str = "read",
        path: str = "",
        latency: float = 0.0,
    ) -> None:
        """Record a Vault request."""
        if not self._enabled:
            return
        with self._lock:
            key = "request_total"
            self._vault_counters.setdefault(key, {})
            label = f"{operation}/{path}"
            self._vault_counters[key][label] = self._vault_counters[key].get(label, 0) + 1

        if _HAS_PROMETHEUS and key in self._vault_prom_counters:
            self._vault_prom_counters[key].labels(
                operation=operation, path=path
            ).inc()

        # Record latency
        latency_key = f"vault_latency_{operation}"
        with self._lock:
            if latency_key not in self._vault_histograms:
                self._vault_histograms[latency_key] = []
            self._vault_histograms[latency_key].append(latency)

        if _HAS_PROMETHEUS and "request_latency" in self._vault_prom_histograms:
            self._vault_prom_histograms["request_latency"].labels(
                operation=operation
            ).observe(latency)

    def record_vault_auth_success(
        self,
        method: str = "token",
    ) -> None:
        """Record Vault authentication success."""
        if not self._enabled:
            return
        with self._lock:
            key = "auth_success_total"
            self._vault_counters.setdefault(key, {})
            self._vault_counters[key][method] = self._vault_counters[key].get(method, 0) + 1

        if _HAS_PROMETHEUS and key in self._vault_prom_counters:
            self._vault_prom_counters[key].labels(method=method).inc()

    def record_vault_auth_failure(
        self,
        method: str = "token",
        reason: str = "unknown",
    ) -> None:
        """Record Vault authentication failure."""
        if not self._enabled:
            return
        with self._lock:
            key = "auth_failure_total"
            self._vault_counters.setdefault(key, {})
            label = f"{method}/{reason}"
            self._vault_counters[key][label] = self._vault_counters[key].get(label, 0) + 1

        if _HAS_PROMETHEUS and key in self._vault_prom_counters:
            self._vault_prom_counters[key].labels(
                method=method, reason=reason
            ).inc()

    def record_vault_lease_renew(
        self,
        status: str = "success",
    ) -> None:
        """Record Vault lease renewal."""
        if not self._enabled:
            return
        with self._lock:
            key = "lease_renew_total"
            self._vault_counters.setdefault(key, {})
            self._vault_counters[key][status] = self._vault_counters[key].get(status, 0) + 1

        if _HAS_PROMETHEUS and key in self._vault_prom_counters:
            self._vault_prom_counters[key].labels(status=status).inc()

    def record_vault_failover(
        self,
        reason: str = "primary_failure",
    ) -> None:
        """Record Vault failover event."""
        if not self._enabled:
            return
        with self._lock:
            key = "failover_total"
            self._vault_counters.setdefault(key, {})
            self._vault_counters[key][reason] = self._vault_counters[key].get(reason, 0) + 1

        if _HAS_PROMETHEUS and key in self._vault_prom_counters:
            self._vault_prom_counters[key].labels(reason=reason).inc()

    def set_vault_active_leases(
        self,
        count: int,
    ) -> None:
        """Set active Vault leases gauge."""
        if not self._enabled:
            return
        self._vault_gauges["active_leases"] = count
        if _HAS_PROMETHEUS and "active_leases" in self._vault_prom_gauges:
            self._vault_prom_gauges["active_leases"].set(count)

    def set_vault_circuit_state(
        self,
        state: int,
    ) -> None:
        """Set Vault circuit breaker state (0=closed, 1=open, 2=half-open)."""
        if not self._enabled:
            return
        self._vault_gauges["circuit_state"] = state
        if _HAS_PROMETHEUS and "circuit_state" in self._vault_prom_gauges:
            self._vault_prom_gauges["circuit_state"].set(state)

    # ── Export ──

    def generate_prometheus(self) -> str:
        """
        Generate Prometheus metrics text format.

        Returns:
            Prometheus text format metrics.
        """
        if _HAS_PROMETHEUS:
            try:
                result = generate_latest()
                if isinstance(result, bytes):
                    result = result.decode("utf-8")
                return result
            except Exception:
                pass

        # Fallback: generate from in-memory data
        lines: List[str] = []

        # Secret counters
        for name, labels in self._counters.items():
            total = sum(labels.values())
            lines.append(f"# HELP {self.METRICS_PREFIX}{name} Total {name}")
            lines.append(f"# TYPE {self.METRICS_PREFIX}{name} counter")
            for label, value in labels.items():
                provider, namespace = label.split("/", 1) if "/" in label else (label, "")
                lines.append(
                    f'{self.METRICS_PREFIX}{name}{{provider="{provider}",namespace="{namespace}"}} {value}'
                )

        # Vault counters
        for name, labels in self._vault_counters.items():
            total = sum(labels.values())
            lines.append(f"# HELP {self.VAULT_METRICS_PREFIX}{name} Total {name}")
            lines.append(f"# TYPE {self.VAULT_METRICS_PREFIX}{name} counter")
            for label, value in labels.items():
                operation, rest = label.split("/", 1) if "/" in label else (label, "")
                lines.append(
                    f'{self.VAULT_METRICS_PREFIX}{name}{{operation="{operation}",path="{rest}"}} {value}'
                )

        # Gauges
        for name, value in self._gauges.items():
            lines.append(f"# HELP {name} Gauge")
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {value}")

        # Vault gauges
        for name, value in self._vault_gauges.items():
            lines.append(f"# HELP {self.VAULT_METRICS_PREFIX}{name} Gauge")
            lines.append(f"# TYPE {self.VAULT_METRICS_PREFIX}{name} gauge")
            lines.append(f"{self.VAULT_METRICS_PREFIX}{name} {value}")

        return "\n".join(lines) + "\n"

    def get_stats(self) -> Dict[str, Any]:
        """Get metrics statistics."""
        with self._lock:
            counters_total = {
                k: sum(v.values()) for k, v in self._counters.items()
            }
            vault_counters_total = {
                k: sum(v.values()) for k, v in self._vault_counters.items()
            }
            return {
                "enabled": self._enabled,
                "counters": counters_total,
                "gauges": dict(self._gauges),
                "histograms": {
                    k: {"count": len(v), "avg": sum(v) / len(v) if v else 0}
                    for k, v in self._histograms.items()
                },
                "vault_counters": vault_counters_total,
                "vault_gauges": dict(self._vault_gauges),
                "vault_histograms": {
                    k: {"count": len(v), "avg": sum(v) / len(v) if v else 0}
                    for k, v in self._vault_histograms.items()
                },
                "has_prometheus": _HAS_PROMETHEUS,
            }
