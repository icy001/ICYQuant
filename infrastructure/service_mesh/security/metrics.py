"""Security metrics for ICYQuant Service Mesh.

Provides ``SecurityMetrics`` for tracking security operations
including authentication, authorization, certificate lifecycle,
mTLS handshakes, denials, and audit events.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SecurityMetrics:
    """Collects and reports security metrics."""

    AUTH_TOTAL = "icyquant_security_auth_total"
    AUTHORIZATION_TOTAL = "icyquant_security_authorization_total"
    CERTIFICATE_ISSUE_TOTAL = "icyquant_certificate_issue_total"
    CERTIFICATE_ROTATION_TOTAL = "icyquant_certificate_rotation_total"
    MTLS_HANDSHAKE_TOTAL = "icyquant_mtls_handshake_total"
    DENIED_TOTAL = "icyquant_security_denied_total"
    AUDIT_TOTAL = "icyquant_security_audit_total"
    CERTIFICATE_ACTIVE = "icyquant_certificate_active"
    IDENTITY_TOTAL = "icyquant_security_identity_total"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}
        self._timers: Dict[str, List[float]] = {}
        self._labels: Dict[str, Dict[str, str]] = {}
        self._start_time = time.monotonic()
        self._register_defaults()

    def _register_defaults(self) -> None:
        for metric in [
            self.AUTH_TOTAL,
            self.AUTHORIZATION_TOTAL,
            self.CERTIFICATE_ISSUE_TOTAL,
            self.CERTIFICATE_ROTATION_TOTAL,
            self.MTLS_HANDSHAKE_TOTAL,
            self.DENIED_TOTAL,
            self.AUDIT_TOTAL,
            self.IDENTITY_TOTAL,
        ]:
            self._counters[metric] = 0
        self._gauges[self.CERTIFICATE_ACTIVE] = 0.0

    def increment_counter(self, name: str, value: int = 1, labels: Optional[Dict[str, str]] = None) -> None:
        with self._lock:
            if name not in self._counters:
                self._counters[name] = 0
            self._counters[name] += value
            if labels:
                self._labels[name] = labels

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        with self._lock:
            self._gauges[name] = value
            if labels:
                self._labels[name] = labels

    def record_timer(self, name: str, duration_s: float, labels: Optional[Dict[str, str]] = None) -> None:
        with self._lock:
            if name not in self._timers:
                self._timers[name] = []
            self._timers[name].append(duration_s)
            if len(self._timers[name]) > 1000:
                self._timers[name] = self._timers[name][-1000:]
            if labels:
                self._labels[name] = labels

    def increment_auth(self, labels: Optional[Dict[str, str]] = None) -> None:
        self.increment_counter(self.AUTH_TOTAL, labels=labels)

    def increment_authorization(self, labels: Optional[Dict[str, str]] = None) -> None:
        self.increment_counter(self.AUTHORIZATION_TOTAL, labels=labels)

    def increment_certificate_issue(self, labels: Optional[Dict[str, str]] = None) -> None:
        self.increment_counter(self.CERTIFICATE_ISSUE_TOTAL, labels=labels)

    def increment_certificate_rotation(self, labels: Optional[Dict[str, str]] = None) -> None:
        self.increment_counter(self.CERTIFICATE_ROTATION_TOTAL, labels=labels)

    def increment_mtls_handshake(self, labels: Optional[Dict[str, str]] = None) -> None:
        self.increment_counter(self.MTLS_HANDSHAKE_TOTAL, labels=labels)

    def increment_denied(self, labels: Optional[Dict[str, str]] = None) -> None:
        self.increment_counter(self.DENIED_TOTAL, labels=labels)

    def increment_audit(self, labels: Optional[Dict[str, str]] = None) -> None:
        self.increment_counter(self.AUDIT_TOTAL, labels=labels)

    def increment_identity(self, labels: Optional[Dict[str, str]] = None) -> None:
        self.increment_counter(self.IDENTITY_TOTAL, labels=labels)

    def set_active_certificates(self, count: int) -> None:
        self.set_gauge(self.CERTIFICATE_ACTIVE, float(count))

    def get_counter(self, name: str) -> int:
        with self._lock:
            return self._counters.get(name, 0)

    def get_gauge(self, name: str) -> float:
        with self._lock:
            return self._gauges.get(name, 0.0)

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            uptime = time.monotonic() - self._start_time
            return {
                "uptime_s": uptime,
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "labels": dict(self._labels),
            }

    def get_stats(self) -> Dict[str, Any]:
        return self.get_summary()

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._timers.clear()
            self._labels.clear()
            self._register_defaults()
            self._start_time = time.monotonic()
