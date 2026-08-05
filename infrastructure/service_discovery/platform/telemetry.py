"""Platform telemetry for ICYQuant service discovery.

Provides ``PlatformTelemetry`` for tracing, logging, and
metrics integration, generating registry timelines, resolver
traces, and failover timelines.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .runtime_context import DiscoveryContext

logger = logging.getLogger(__name__)


class PlatformTelemetry:
    """Telemetry integration for the discovery platform.

    Provides distributed tracing spans for registry, resolver,
    and failover operations, plus structured logging and metrics
    bridge.
    """

    def __init__(
        self, context: Optional[DiscoveryContext] = None
    ) -> None:
        self._lock = threading.RLock()
        self._context = context or DiscoveryContext()
        self._traces: List[Dict[str, Any]] = []
        self._spans: Dict[str, List[Dict[str, Any]]] = {}
        self._max_history = 1000
        self._trace_count = 0
        self._span_count = 0

    def start_span(
        self,
        name: str,
        service_name: str = "",
        data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Start a new tracing span.

        Args:
            name: Span name.
            service_name: Associated service.
            data: Optional span data.

        Returns:
            Span ID.
        """
        import uuid

        span_id = str(uuid.uuid4())[:8]
        span: Dict[str, Any] = {
            "span_id": span_id,
            "name": name,
            "service_name": service_name,
            "data": dict(data) if data else {},
            "start_time": datetime.utcnow().isoformat(),
            "end_time": None,
            "status": "active",
        }
        with self._lock:
            key = service_name or "__global__"
            if key not in self._spans:
                self._spans[key] = []
            self._spans[key].append(span)
            self._span_count += 1
        return span_id

    def end_span(
        self, span_id: str, status: str = "success"
    ) -> None:
        with self._lock:
            for key in self._spans:
                for span in self._spans[key]:
                    if span["span_id"] == span_id:
                        span["end_time"] = (
                            datetime.utcnow().isoformat()
                        )
                        span["status"] = status
                        return

    def record_trace(
        self,
        trace_type: str,
        service_name: str = "",
        data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a platform trace event.

        Args:
            trace_type: Trace type (e.g. 'registry', 'failover').
            service_name: Associated service.
            data: Trace data.

        Returns:
            Trace ID.
        """
        import uuid

        trace_id = str(uuid.uuid4())[:8]
        trace: Dict[str, Any] = {
            "trace_id": trace_id,
            "type": trace_type,
            "service_name": service_name,
            "data": dict(data) if data else {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        with self._lock:
            self._traces.append(trace)
            self._trace_count += 1
            if len(self._traces) > self._max_history:
                self._traces = self._traces[-self._max_history:]

        logger.debug(
            "Trace recorded: %s/%s (id=%s).",
            trace_type,
            service_name,
            trace_id,
        )
        return trace_id

    def record_registry_timeline(
        self, service_name: str, event: str, data: Any = None
    ) -> str:
        return self.record_trace(
            "registry", service_name, {"event": event, "data": str(data)[:200] if data else None}
        )

    def record_resolver_trace(
        self, service_name: str, data: Any = None
    ) -> str:
        return self.record_trace(
            "resolver", service_name, {"data": str(data)[:200] if data else None}
        )

    def record_failover_timeline(
        self, service_name: str, data: Any = None
    ) -> str:
        return self.record_trace(
            "failover", service_name, {"data": str(data)[:200] if data else None}
        )

    def get_traces(
        self,
        trace_type: Optional[str] = None,
        service_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            traces = list(self._traces)
        if trace_type:
            traces = [
                t for t in traces if t["type"] == trace_type
            ]
        if service_name:
            traces = [
                t
                for t in traces
                if t.get("service_name") == service_name
            ]
        return traces

    def get_spans(
        self, service_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        with self._lock:
            if service_name:
                return list(self._spans.get(service_name, []))
            result: List[Dict[str, Any]] = []
            for spans in self._spans.values():
                result.extend(spans)
            return result

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "trace_count": self._trace_count,
                "span_count": self._span_count,
                "trace_history_size": len(self._traces),
                "span_services": sorted(self._spans.keys()),
                "traces_by_type": self._count_by_type(),
            }

    def _count_by_type(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for t in self._traces:
            tp = t.get("type", "unknown")
            counts[tp] = counts.get(tp, 0) + 1
        return counts

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"PlatformTelemetry(traces={self._trace_count}, "
                f"spans={self._span_count})"
            )
