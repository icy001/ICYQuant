"""Telemetry for ICYQuant service discovery.

Provides ``ServiceDiscoveryTelemetry`` for recording heartbeat,
health check, lease, and recovery events, plus lightweight
distributed tracing via spans and traces. Thread-safe.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)


class ServiceDiscoveryTelemetry:
    """Telemetry collector for service discovery operations.

    Tracks counters for heartbeat, health check, lease, and recovery
    events, and maintains a bounded ring of spans grouped into
    traces. Thread-safe via a reentrant lock.

    Args:
        max_spans: Maximum number of spans to retain.
    """

    def __init__(self, max_spans: int = 10000) -> None:
        self._lock = threading.RLock()
        self._max_spans = max(int(max_spans), 1)
        self._spans: Deque[Dict[str, Any]] = deque()
        self._open_spans: Dict[str, Dict[str, Any]] = {}
        self._counters: Dict[str, Dict[str, int]] = defaultdict(dict)
        self._latencies: Dict[str, List[float]] = defaultdict(list)
        self._max_latency_samples = 1000

    # ── Counters ──

    def record_heartbeat(
        self,
        service_name: str,
        instance_id: str,
        latency: float,
        success: bool,
    ) -> None:
        """Record a heartbeat event."""
        with self._lock:
            self._increment(
                "heartbeat_total", service_name
            )
            if success:
                self._increment(
                    "heartbeat_success_total", service_name
                )
            else:
                self._increment(
                    "heartbeat_failure_total", service_name
                )
            self._record_latency("heartbeat_latency_ms", latency)
        logger.debug(
            "Telemetry: heartbeat for '%s/%s' (success=%s, latency=%.4fs).",
            service_name,
            instance_id,
            success,
            latency,
        )

    def record_health_check(
        self,
        service_name: str,
        instance_id: str,
        probe_type: str,
        latency: float,
        success: bool,
    ) -> None:
        """Record a health-check event."""
        with self._lock:
            self._increment(
                "health_check_total", service_name
            )
            label = probe_type or "unknown"
            self._increment(
                "health_check_by_probe", label
            )
            if success:
                self._increment(
                    "health_check_success_total", service_name
                )
            else:
                self._increment(
                    "health_check_failure_total", service_name
                )
            self._record_latency("health_check_latency_ms", latency)

    def record_lease_event(
        self,
        event_type: str,
        service_name: str,
        instance_id: str,
    ) -> None:
        """Record a lease lifecycle event."""
        with self._lock:
            label = event_type or "unknown"
            self._increment("lease_event_total", label)
            self._increment("lease_event_by_service", service_name)

    def record_recovery(
        self,
        service_name: str,
        instance_id: str,
        success: bool,
    ) -> None:
        """Record a recovery attempt."""
        with self._lock:
            self._increment("recovery_total", service_name)
            if success:
                self._increment("recovery_success_total", service_name)
            else:
                self._increment("recovery_failure_total", service_name)

    # ── Tracing ──

    def start_span(
        self,
        operation: str,
        service_name: str = None,
    ) -> str:
        """Start a new telemetry span.

        Args:
            operation: Operation name (e.g. ``register``, ``discover``).
            service_name: Optional service name to associate.

        Returns:
            The span identifier.
        """
        span_id = uuid.uuid4().hex
        now = time.time()
        span = {
            "span_id": span_id,
            "trace_id": span_id,
            "operation": operation or "unknown",
            "service_name": service_name or "",
            "start_time": now,
            "start_time_iso": datetime.utcfromtimestamp(now).isoformat(),
            "end_time": None,
            "duration_ms": None,
            "status": "in_progress",
        }
        with self._lock:
            self._open_spans[span_id] = span
        return span_id

    def end_span(self, span_id: str, status: str = "ok") -> None:
        """End an open telemetry span.

        Args:
            span_id: The span identifier returned by :meth:`start_span`.
            status: Span outcome (``ok``, ``error``, ``cancelled``).
        """
        now = time.time()
        with self._lock:
            span = self._open_spans.pop(span_id, None)
            if span is None:
                logger.warning(
                    "Telemetry: unknown span_id '%s'.", span_id
                )
                return
            span["end_time"] = now
            span["end_time_iso"] = datetime.utcfromtimestamp(now).isoformat()
            span["duration_ms"] = (now - span["start_time"]) * 1000.0
            span["status"] = status or "ok"
            self._spans.append(span)
            if len(self._spans) > self._max_spans:
                self._spans.popleft()
            self._record_latency(
                f"span_{span['operation']}_ms", span["duration_ms"]
            )

    def get_spans(
        self, service_name: str = None
    ) -> List[Dict[str, Any]]:
        """Return completed spans, optionally filtered by service."""
        with self._lock:
            spans = list(self._spans)
            open_spans = [
                dict(s) for s in self._open_spans.values()
            ]
        all_spans = open_spans + spans
        if service_name is None:
            return all_spans
        return [s for s in all_spans if s.get("service_name") == service_name]

    def get_traces(
        self, service_name: str = None
    ) -> List[Dict[str, Any]]:
        """Return traces (groups of spans), optionally filtered by service.

        Each trace is a dictionary with ``trace_id``, ``service_name``,
        and a list of ``spans``.
        """
        spans = self.get_spans(service_name)
        traces: Dict[str, Dict[str, Any]] = {}
        for span in spans:
            trace_id = span.get("trace_id", span.get("span_id", ""))
            trace = traces.setdefault(
                trace_id,
                {"trace_id": trace_id, "service_name": span.get("service_name", ""), "spans": []},
            )
            trace["spans"].append(span)
        return list(traces.values())

    # ── Stats ──

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the telemetry collector."""
        with self._lock:
            counters = {
                name: dict(entries)
                for name, entries in self._counters.items()
            }
            latencies = {
                name: self._summarize(values)
                for name, values in self._latencies.items()
            }
            return {
                "open_span_count": len(self._open_spans),
                "completed_span_count": len(self._spans),
                "max_spans": self._max_spans,
                "counters": counters,
                "latencies": latencies,
            }

    # ── Internal helpers ──

    def _increment(self, name: str, label: str, value: int = 1) -> None:
        key = label or "__total__"
        self._counters[name][key] = (
            self._counters[name].get(key, 0) + int(value)
        )

    def _record_latency(self, name: str, latency: float) -> None:
        samples = self._latencies[name]
        samples.append(float(latency))
        if len(samples) > self._max_latency_samples:
            del samples[: len(samples) - self._max_latency_samples]

    @staticmethod
    def _summarize(values: List[float]) -> Dict[str, float]:
        if not values:
            return {"avg": 0.0, "min": 0.0, "max": 0.0, "count": 0}
        return {
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "count": len(values),
        }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"ServiceDiscoveryTelemetry(spans={len(self._spans)}, "
                f"open={len(self._open_spans)})"
            )
