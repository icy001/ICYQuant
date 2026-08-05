"""Distributed tracing for service discovery resolution.

Provides ``ResolverTelemetry`` which records spans and traces
for service resolution operations, enabling observability
and debugging of the resolution pipeline.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import deque
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_SPANS = 5000
_MAX_TRACES = 1000


class ResolverTelemetry:
    """Collects spans and traces for service resolution.

    Supports recording resolve operations, routing decisions,
    and span-based tracing for distributed observability.

    Usage::

        telemetry = ResolverTelemetry()
        span_id = telemetry.start_span("resolve", "payment")
        telemetry.end_span(span_id, "ok")
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._spans: Deque[Dict[str, Any]] = deque(maxlen=_MAX_SPANS)
        self._traces: Deque[Dict[str, Any]] = deque(maxlen=_MAX_TRACES)
        self._active_spans: Dict[str, Dict[str, Any]] = {}
        self._resolve_count = 0
        self._route_decision_count = 0
        self._span_count = 0
        self._trace_count = 0

    def record_resolve(
        self,
        service_name: str,
        strategy: str,
        instance_id: str,
        latency: float,
    ) -> None:
        """Record a service resolution.

        Args:
            service_name: The resolved service name.
            strategy: The strategy used.
            instance_id: The selected instance.
            latency: Resolution latency in seconds.
        """
        entry: Dict[str, Any] = {
            "service_name": service_name,
            "strategy": strategy,
            "instance_id": instance_id,
            "latency": float(latency),
            "timestamp": time.time(),
            "type": "resolve",
        }
        with self._lock:
            self._resolve_count += 1
            self._spans.append(entry)
            self._traces.append(entry)

    def record_route_decision(
        self,
        route_type: str,
        service_name: str,
        candidates: int,
        selected: str = None,
    ) -> None:
        """Record a routing decision.

        Args:
            route_type: The type of routing applied.
            service_name: The service being routed.
            candidates: Number of candidate instances.
            selected: The selected instance ID.
        """
        entry: Dict[str, Any] = {
            "route_type": route_type,
            "service_name": service_name,
            "candidates": int(candidates),
            "selected": selected,
            "timestamp": time.time(),
            "type": "route_decision",
        }
        with self._lock:
            self._route_decision_count += 1
            self._spans.append(entry)
            self._traces.append(entry)

    def start_span(
        self,
        operation: str,
        service_name: str = None,
    ) -> str:
        """Start a new tracing span.

        Args:
            operation: The operation name (e.g., "resolve",
                "load_balance").
            service_name: Optional service name.

        Returns:
            A unique span identifier.
        """
        span_id = uuid.uuid4().hex
        span: Dict[str, Any] = {
            "span_id": span_id,
            "operation": operation,
            "service_name": service_name,
            "start_time": time.time(),
            "end_time": None,
            "status": "pending",
            "type": "span",
        }
        with self._lock:
            self._active_spans[span_id] = span
            self._span_count += 1
        logger.debug(
            "Span started: id=%s op=%s service=%s",
            span_id,
            operation,
            service_name,
        )
        return span_id

    def end_span(
        self, span_id: str, status: str = "ok"
    ) -> None:
        """End a tracing span.

        Args:
            span_id: The span identifier from ``start_span``.
            status: The span status (e.g., "ok", "error").
        """
        with self._lock:
            span = self._active_spans.pop(span_id, None)
            if span is None:
                logger.warning(
                    "Span '%s' not found for ending.", span_id
                )
                return
            span["end_time"] = time.time()
            span["status"] = status
            elapsed = span["end_time"] - span["start_time"]
            span["duration"] = elapsed
            self._spans.append(span)
            self._traces.append(span)
            self._trace_count += 1
        logger.debug(
            "Span ended: id=%s status=%s duration=%.4f",
            span_id,
            status,
            elapsed,
        )

    def get_spans(
        self, service_name: str = None
    ) -> List[Dict[str, Any]]:
        """Retrieve recorded spans.

        Args:
            service_name: If provided, filter spans to this
                service.

        Returns:
            A list of span entries, most recent first.
        """
        with self._lock:
            entries = list(self._spans)
        if service_name is not None:
            entries = [
                e
                for e in entries
                if e.get("service_name") == service_name
            ]
        entries.reverse()
        return entries

    def get_traces(
        self, service_name: str = None
    ) -> List[Dict[str, Any]]:
        """Retrieve recorded traces.

        Args:
            service_name: If provided, filter traces to this
                service.

        Returns:
            A list of trace entries, most recent first.
        """
        with self._lock:
            entries = list(self._traces)
        if service_name is not None:
            entries = [
                e
                for e in entries
                if e.get("service_name") == service_name
            ]
        entries.reverse()
        return entries

    def get_stats(self) -> Dict[str, Any]:
        """Return telemetry statistics.

        Returns:
            A dictionary with counts and buffer sizes.
        """
        with self._lock:
            return {
                "telemetry": "ResolverTelemetry",
                "resolve_count": self._resolve_count,
                "route_decision_count": self._route_decision_count,
                "span_count": self._span_count,
                "trace_count": self._trace_count,
                "active_spans": len(self._active_spans),
                "spans_size": len(self._spans),
                "traces_size": len(self._traces),
                "max_spans": _MAX_SPANS,
                "max_traces": _MAX_TRACES,
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"ResolverTelemetry(resolves={self._resolve_count}, "
                f"traces={self._trace_count})"
            )