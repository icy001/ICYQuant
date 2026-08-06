"""Security telemetry for ICYQuant Service Mesh.

Provides ``SecurityTelemetry`` for structured logging of security
events including auth decisions, certificate lifecycle, mTLS
handshakes, and policy evaluations.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SecurityTelemetry:
    """Telemetry for security operations."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._events: List[Dict[str, Any]] = []
        self._max_events = 5000
        self._event_count = 0

    def log_authentication(self, principal: str, method: str, success: bool, metadata: Optional[Dict[str, Any]] = None) -> None:
        with self._lock:
            self._event_count += 1
            self._add_event({
                "type": "authentication",
                "principal": principal,
                "method": method,
                "success": success,
                "metadata": metadata or {},
                "timestamp": datetime.utcnow().isoformat(),
            })

    def log_authorization(self, principal: str, resource: str, action: str, allowed: bool, policy_id: str = "") -> None:
        with self._lock:
            self._event_count += 1
            self._add_event({
                "type": "authorization",
                "principal": principal,
                "resource": resource,
                "action": action,
                "allowed": allowed,
                "policy_id": policy_id,
                "timestamp": datetime.utcnow().isoformat(),
            })

    def log_certificate_event(self, event: str, cert_id: str, details: Optional[Dict[str, Any]] = None) -> None:
        with self._lock:
            self._event_count += 1
            self._add_event({
                "type": "certificate",
                "event": event,
                "cert_id": cert_id,
                "details": details or {},
                "timestamp": datetime.utcnow().isoformat(),
            })

    def log_mtls_handshake(self, client_identity: str, server_identity: str, success: bool, duration_s: float = 0.0) -> None:
        with self._lock:
            self._event_count += 1
            self._add_event({
                "type": "mtls_handshake",
                "client_identity": client_identity,
                "server_identity": server_identity,
                "success": success,
                "duration_s": duration_s,
                "timestamp": datetime.utcnow().isoformat(),
            })

    def log_policy_evaluation(self, policy_id: str, principal: str, result: str, details: Optional[Dict[str, Any]] = None) -> None:
        with self._lock:
            self._event_count += 1
            self._add_event({
                "type": "policy_evaluation",
                "policy_id": policy_id,
                "principal": principal,
                "result": result,
                "details": details or {},
                "timestamp": datetime.utcnow().isoformat(),
            })

    def log_security_event(self, event: str, component: str, severity: str = "info", details: Optional[Dict[str, Any]] = None) -> None:
        with self._lock:
            self._event_count += 1
            self._add_event({
                "type": "security_event",
                "event": event,
                "component": component,
                "severity": severity,
                "details": details or {},
                "timestamp": datetime.utcnow().isoformat(),
            })

    def _add_event(self, event: Dict[str, Any]) -> None:
        event["seq"] = self._event_count
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]

    def get_events(self, event_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            events = list(self._events)
        if event_type:
            events = [e for e in events if e["type"] == event_type]
        return events[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "event_count": self._event_count,
                "stored_events": len(self._events),
            }

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
            self._event_count = 0
