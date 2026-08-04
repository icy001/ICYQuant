"""
Crypto metrics collection.

Provides Prometheus-compatible metrics
for cryptographic operations including
encryption, decryption, signing, and
key rotation statistics.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List

from .constants import METRICS_PREFIX

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Gauge, Histogram, generate_latest
    _HAS_PROMETHEUS = True
except ImportError:
    _HAS_PROMETHEUS = False


class CryptoMetrics:
    """
    Crypto metrics collector.

    Tracks cryptographic operations with
    Prometheus-compatible metrics and
    in-memory fallbacks when Prometheus
    is not available.

    Metrics:
    - icyquant_crypto_encrypt_total
    - icyquant_crypto_decrypt_total
    - icyquant_crypto_sign_total
    - icyquant_crypto_verify_total
    - icyquant_crypto_hash_total
    - icyquant_crypto_key_rotation_total
    - icyquant_crypto_failure_total
    - icyquant_crypto_latency_seconds
    """

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled
        self._lock = threading.Lock()

        # In-memory counters
        self._counters: Dict[str, Dict[str, float]] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._gauges: Dict[str, float] = {}

        # Prometheus metrics
        self._prom_counters: Dict[str, Any] = {}
        self._prom_histograms: Dict[str, Any] = {}
        self._prom_gauges: Dict[str, Any] = {}

        if enabled and _HAS_PROMETHEUS:
            self._init_prometheus()

    def _init_prometheus(self) -> None:
        """Initialize Prometheus metrics."""
        try:
            self._prom_counters["encrypt_total"] = Counter(
                f"{METRICS_PREFIX}encrypt_total",
                "Total encryption operations",
                ["algorithm", "mode"],
            )
            self._prom_counters["decrypt_total"] = Counter(
                f"{METRICS_PREFIX}decrypt_total",
                "Total decryption operations",
                ["algorithm", "mode"],
            )
            self._prom_counters["sign_total"] = Counter(
                f"{METRICS_PREFIX}sign_total",
                "Total signing operations",
                ["algorithm"],
            )
            self._prom_counters["verify_total"] = Counter(
                f"{METRICS_PREFIX}verify_total",
                "Total verification operations",
                ["algorithm", "result"],
            )
            self._prom_counters["hash_total"] = Counter(
                f"{METRICS_PREFIX}hash_total",
                "Total hash operations",
                ["algorithm"],
            )
            self._prom_counters["key_rotation_total"] = Counter(
                f"{METRICS_PREFIX}key_rotation_total",
                "Total key rotation operations",
                ["provider", "result"],
            )
            self._prom_counters["failure_total"] = Counter(
                f"{METRICS_PREFIX}failure_total",
                "Total failed operations",
                ["operation", "reason"],
            )

            self._prom_histograms["latency"] = Histogram(
                f"{METRICS_PREFIX}latency_seconds",
                "Operation latency in seconds",
                ["operation"],
            )

            self._prom_gauges["active_operations"] = Gauge(
                f"{METRICS_PREFIX}active_operations",
                "Number of active crypto operations",
            )
            self._prom_gauges["active_keys"] = Gauge(
                f"{METRICS_PREFIX}active_keys",
                "Number of active keys",
            )
            self._prom_gauges["kms_operations"] = Gauge(
                f"{METRICS_PREFIX}kms_operations",
                "Number of in-flight KMS operations",
            )
        except Exception:
            self._prom_counters.clear()
            self._prom_histograms.clear()
            self._prom_gauges.clear()

    def record_encrypt(
        self,
        algorithm: str = "",
        mode: str = "envelope",
        success: bool = True,
        duration: float = 0.0,
        failure_reason: str = "",
    ) -> None:
        """Record an encryption operation."""
        self._record_counter(
            "encrypt_total", f"{algorithm}/{mode}"
        )
        if not success:
            self._record_failure("encrypt", failure_reason)
        if duration > 0:
            self._record_latency("encrypt", duration)

    def record_decrypt(
        self,
        algorithm: str = "",
        mode: str = "envelope",
        success: bool = True,
        duration: float = 0.0,
        failure_reason: str = "",
    ) -> None:
        """Record a decryption operation."""
        self._record_counter(
            "decrypt_total", f"{algorithm}/{mode}"
        )
        if not success:
            self._record_failure("decrypt", failure_reason)
        if duration > 0:
            self._record_latency("decrypt", duration)

    def record_sign(
        self,
        algorithm: str = "",
        success: bool = True,
        duration: float = 0.0,
        failure_reason: str = "",
    ) -> None:
        """Record a signing operation."""
        self._record_counter("sign_total", algorithm)
        if not success:
            self._record_failure("sign", failure_reason)
        if duration > 0:
            self._record_latency("sign", duration)

    def record_verify(
        self,
        algorithm: str = "",
        result: str = "pass",
        duration: float = 0.0,
    ) -> None:
        """Record a verification operation."""
        self._record_counter("verify_total", f"{algorithm}/{result}")
        if duration > 0:
            self._record_latency("verify", duration)

    def record_hash(
        self,
        algorithm: str = "",
        duration: float = 0.0,
    ) -> None:
        """Record a hash operation."""
        self._record_counter("hash_total", algorithm)
        if duration > 0:
            self._record_latency("hash", duration)

    def record_key_rotation(
        self,
        provider: str = "",
        result: str = "success",
        duration: float = 0.0,
    ) -> None:
        """Record a key rotation."""
        self._record_counter("key_rotation_total", f"{provider}/{result}")
        if duration > 0:
            self._record_latency("rotate", duration)

    def set_active_operations(self, count: int) -> None:
        """Set active operations count."""
        self._gauges["active_operations"] = count
        if _HAS_PROMETHEUS and "active_operations" in self._prom_gauges:
            self._prom_gauges["active_operations"].set(count)

    def set_active_keys(self, count: int) -> None:
        """Set active keys count."""
        self._gauges["active_keys"] = count
        if _HAS_PROMETHEUS and "active_keys" in self._prom_gauges:
            self._prom_gauges["active_keys"].set(count)

    def set_kms_operations(self, count: int) -> None:
        """Set KMS operations count."""
        self._gauges["kms_operations"] = count
        if _HAS_PROMETHEUS and "kms_operations" in self._prom_gauges:
            self._prom_gauges["kms_operations"].set(count)

    def _record_counter(
        self,
        name: str,
        label: str,
    ) -> None:
        """Record a counter increment."""
        if not self._enabled:
            return

        with self._lock:
            self._counters.setdefault(name, {})
            self._counters[name][label] = (
                self._counters[name].get(label, 0) + 1
            )

        if _HAS_PROMETHEUS and name in self._prom_counters:
            try:
                labels = self._parse_labels(name, label)
                if labels:
                    self._prom_counters[name].labels(**labels).inc()
                else:
                    self._prom_counters[name].inc()
            except Exception:
                try:
                    self._prom_counters[name].inc()
                except Exception:
                    pass

    def _parse_labels(
        self,
        counter_name: str,
        label_str: str,
    ) -> Dict[str, str]:
        """Parse label string into keyword dict for Prometheus."""
        mappings = {
            "encrypt_total": ["algorithm", "mode"],
            "decrypt_total": ["algorithm", "mode"],
            "sign_total": ["algorithm"],
            "verify_total": ["algorithm", "result"],
            "hash_total": ["algorithm"],
            "key_rotation_total": ["provider", "result"],
            "failure_total": ["operation", "reason"],
        }
        label_keys = mappings.get(counter_name, [])
        if not label_keys:
            return {}

        parts = label_str.split("/")
        result: Dict[str, str] = {}
        for i, key in enumerate(label_keys):
            result[key] = parts[i] if i < len(parts) else ""
        return result

    def _record_failure(
        self,
        operation: str,
        reason: str,
    ) -> None:
        """Record a failure."""
        if not self._enabled:
            return

        with self._lock:
            key = f"{operation}/{reason}"
            self._counters.setdefault("failure_total", {})
            self._counters["failure_total"][key] = (
                self._counters["failure_total"].get(key, 0) + 1
            )

        if _HAS_PROMETHEUS and "failure_total" in self._prom_counters:
            try:
                self._prom_counters["failure_total"].labels(
                    operation=operation,
                    reason=reason or "unknown",
                ).inc()
            except Exception:
                self._prom_counters["failure_total"].inc()

    def _record_latency(
        self,
        operation: str,
        duration: float,
    ) -> None:
        """Record operation latency."""
        if not self._enabled:
            return

        with self._lock:
            key = f"latency_{operation}"
            if key not in self._histograms:
                self._histograms[key] = []
            self._histograms[key].append(duration)

        if _HAS_PROMETHEUS and "latency" in self._prom_histograms:
            try:
                self._prom_histograms["latency"].labels(
                    operation=operation,
                ).observe(duration)
            except Exception:
                pass

    def _get_label_key(self, name: str) -> str:
        """Get label key for counter name."""
        mapping = {
            "encrypt_total": "algorithm",
            "decrypt_total": "algorithm",
            "sign_total": "algorithm",
            "verify_total": "algorithm",
            "hash_total": "algorithm",
            "key_rotation_total": "provider",
        }
        return mapping.get(name, "label")

    def generate_prometheus(self) -> str:
        """Generate Prometheus text format metrics."""
        if _HAS_PROMETHEUS:
            try:
                result = generate_latest()
                if isinstance(result, bytes):
                    result = result.decode("utf-8")
                return result
            except Exception:
                pass

        lines: List[str] = []
        for name, labels in self._counters.items():
            total = sum(labels.values())
            lines.append(f"# HELP {METRICS_PREFIX}{name} Total {name}")
            lines.append(f"# TYPE {METRICS_PREFIX}{name} counter")
            for label, value in labels.items():
                parts = label.split("/", 1) if "/" in label else (label, "")
                lines.append(
                    f'{METRICS_PREFIX}{name}{{label="{label}"}} {value}'
                )

        for name, value in self._gauges.items():
            lines.append(f"# HELP {METRICS_PREFIX}{name} Gauge")
            lines.append(f"# TYPE {METRICS_PREFIX}{name} gauge")
            lines.append(f"{METRICS_PREFIX}{name} {value}")

        return "\n".join(lines) + "\n"

    def get_stats(self) -> Dict[str, Any]:
        """Get metrics statistics."""
        with self._lock:
            return {
                "enabled": self._enabled,
                "counters": {
                    k: sum(v.values()) for k, v in self._counters.items()
                },
                "gauges": dict(self._gauges),
                "histograms": {
                    k: {
                        "count": len(v),
                        "avg": sum(v) / len(v) if v else 0,
                        "max": max(v) if v else 0,
                    }
                    for k, v in self._histograms.items()
                },
                "has_prometheus": _HAS_PROMETHEUS,
            }
