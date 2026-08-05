"""Traffic telemetry for ICYQuant Service Mesh.

Provides ``TrafficTelemetry`` for structured logging, tracing,
and metrics emission for traffic management events including
route decisions, retry chains, and circuit breaker status.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TrafficTelemetry:
    """Telemetry for traffic management operations."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._events: List[Dict[str, Any]] = []
        self._max_events = 5000
        self._trace_id_counter = 0
        self._event_count = 0
        self._tracing_enabled = True

    def log_route_decision(
        self,
        route_id: str,
        service: str,
        destination: str,
        matched: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a routing decision."""
        with self._lock:
            self._event_count += 1
            event = {
                "type": "route_decision",
                "route_id": route_id,
                "service": service,
                "destination": destination,
                "matched": matched,
                "metadata": metadata or {},
                "timestamp": datetime.utcnow().isoformat(),
                "seq": self._event_count,
            }
            self._add_event(event)

    def log_retry_chain(
        self,
        route_id: str,
        attempt: int,
        max_retries: int,
        reason: str,
        duration_s: float,
    ) -> None:
        """Log a retry event in a retry chain."""
        with self._lock:
            self._event_count += 1
            event = {
                "type": "retry",
                "route_id": route_id,
                "attempt": attempt,
                "max_retries": max_retries,
                "reason": reason,
                "duration_s": duration_s,
                "timestamp": datetime.utcnow().isoformat(),
                "seq": self._event_count,
            }
            self._add_event(event)

    def log_circuit_status(
        self,
        target: str,
        old_state: str,
        new_state: str,
        reason: str = "",
    ) -> None:
        """Log a circuit breaker state transition."""
        with self._lock:
            self._event_count += 1
            event = {
                "type": "circuit_status",
                "target": target,
                "old_state": old_state,
                "new_state": new_state,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
                "seq": self._event_count,
            }
            self._add_event(event)

    def log_request(
        self,
        method: str,
        path: str,
        route_id: str,
        target: str,
        status_code: int,
        duration_s: float,
        retries: int = 0,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a proxied request."""
        with self._lock:
            self._event_count += 1
            event = {
                "type": "request",
                "method": method,
                "path": path,
                "route_id": route_id,
                "target": target,
                "status_code": status_code,
                "duration_s": duration_s,
                "retries": retries,
                "extra": extra or {},
                "timestamp": datetime.utcnow().isoformat(),
                "seq": self._event_count,
            }
            self._add_event(event)

    def log_mirror(
        self,
        source: str,
        mirror: str,
        success: bool,
        duration_s: float,
    ) -> None:
        """Log a mirror request."""
        with self._lock:
            self._event_count += 1
            event = {
                "type": "mirror",
                "source": source,
                "mirror": mirror,
                "success": success,
                "duration_s": duration_s,
                "timestamp": datetime.utcnow().isoformat(),
                "seq": self._event_count,
            }
            self._add_event(event)

    def log_canary(
        self,
        route_id: str,
        is_canary: bool,
        percentage: int,
    ) -> None:
        """Log a canary routing decision."""
        with self._lock:
            self._event_count += 1
            event = {
                "type": "canary",
                "route_id": route_id,
                "is_canary": is_canary,
                "percentage": percentage,
                "timestamp": datetime.utcnow().isoformat(),
                "seq": self._event_count,
            }
            self._add_event(event)

    def log_blue_green(
        self,
        route_id: str,
        target: str,
        version: str,
        phase: str,
    ) -> None:
        """Log a blue-green deployment event."""
        with self._lock:
            self._event_count += 1
            event = {
                "type": "blue_green",
                "route_id": route_id,
                "target": target,
                "version": version,
                "phase": phase,
                "timestamp": datetime.utcnow().isoformat(),
                "seq": self._event_count,
            }
            self._add_event(event)

    def log_rate_limit(
        self,
        target: str,
        client_id: str,
        rate: float,
        burst: int,
    ) -> None:
        """Log a rate limiting event."""
        with self._lock:
            self._event_count += 1
            event = {
                "type": "rate_limit",
                "target": target,
                "client_id": client_id,
                "rate": rate,
                "burst": burst,
                "timestamp": datetime.utcnow().isoformat(),
                "seq": self._event_count,
            }
            self._add_event(event)

    def _add_event(self, event: Dict[str, Any]) -> None:
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]

    def generate_trace_id(self) -> str:
        with self._lock:
            self._trace_id_counter += 1
            return f"tr-{int(time.time())}-{self._trace_id_counter}"

    def get_events(
        self,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
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
                "tracing_enabled": self._tracing_enabled,
            }

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
            self._event_count = 0
            self._trace_id_counter = 0