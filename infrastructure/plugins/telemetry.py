from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PluginTelemetry:
    """Observability: audit trails, trace spans, and metrics labels.

    Provides structured event recording, distributed tracing with
    span lifecycle management, and audit trail retrieval for
    compliance and debugging.

    Usage::

        telemetry = PluginTelemetry()
        span_id = telemetry.start_span("install_plugin", plugin_id="my_plugin")
        telemetry.record_event("installed", "my_plugin", {"version": "1.0"})
        telemetry.end_span(span_id, status="ok")
        audit = telemetry.get_audit_trail("my_plugin")
    """

    def __init__(self) -> None:
        self._events: List[Dict[str, Any]] = []
        self._spans: Dict[str, Dict[str, Any]] = {}
        self._traces: Dict[str, List[str]] = {}
        self._audit: Dict[str, List[Dict[str, Any]]] = {}
        self._event_count: int = 0
        self._span_count: int = 0
        self._max_events: int = 10000
        self._max_spans: int = 5000

    def record_event(
        self,
        event_type: str,
        plugin_id: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a telemetry event.

        Args:
            event_type: The type of event (e.g. ``installed``).
            plugin_id: The plugin identifier.
            data: Optional event data.
        """
        try:
            event: Dict[str, Any] = {
                "event_id": str(uuid.uuid4()),
                "event_type": event_type,
                "plugin_id": plugin_id,
                "data": dict(data or {}),
                "timestamp": time.monotonic(),
                "iso_timestamp": time.strftime(
                    "%Y-%m-%dT%H:%M:%S", time.gmtime()
                ),
            }
            self._events.append(event)
            self._event_count += 1

            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]

            audit_entry = {
                "event_type": event_type,
                "timestamp": event["timestamp"],
                "data": dict(data or {}),
            }
            self._audit.setdefault(plugin_id, []).append(audit_entry)

            logger.debug(
                "Recorded event '%s' for '%s'.", event_type, plugin_id
            )
        except Exception as e:
            logger.error(
                "Failed to record event '%s' for '%s': %s",
                event_type,
                plugin_id,
                e,
            )

    def start_span(
        self, operation: str, plugin_id: Optional[str] = None
    ) -> str:
        """Start a new trace span.

        Args:
            operation: The operation name (e.g. ``load_plugin``).
            plugin_id: Optional plugin identifier.

        Returns:
            The unique span ID.
        """
        span_id = str(uuid.uuid4())
        try:
            trace_id = str(uuid.uuid4())
            span: Dict[str, Any] = {
                "span_id": span_id,
                "trace_id": trace_id,
                "operation": operation,
                "plugin_id": plugin_id or "",
                "status": "active",
                "start_time": time.monotonic(),
                "end_time": None,
                "duration": None,
                "tags": {},
            }
            self._spans[span_id] = span
            self._span_count += 1

            self._traces.setdefault(trace_id, []).append(span_id)

            if len(self._spans) > self._max_spans:
                oldest_keys = sorted(
                    self._spans.keys(),
                    key=lambda k: self._spans[k]["start_time"],
                )
                for old_key in oldest_keys[: len(self._spans) - self._max_spans]:
                    del self._spans[old_key]

            logger.debug(
                "Started span '%s' for operation '%s'.",
                span_id,
                operation,
            )
        except Exception as e:
            logger.error(
                "Failed to start span for operation '%s': %s",
                operation,
                e,
            )

        return span_id

    def end_span(self, span_id: str, status: str = "ok") -> None:
        """End a trace span with a status.

        Args:
            span_id: The span identifier returned by :meth:`start_span`.
            status: The completion status (e.g. ``ok``, ``error``).
        """
        span = self._spans.get(span_id)
        if span is None:
            logger.warning("Span '%s' not found.", span_id)
            return

        try:
            end_time = time.monotonic()
            span["status"] = status
            span["end_time"] = end_time
            span["duration"] = end_time - span["start_time"]

            logger.debug(
                "Ended span '%s' with status '%s' (%.4fs).",
                span_id,
                status,
                span["duration"],
            )
        except Exception as e:
            logger.error(
                "Failed to end span '%s': %s", span_id, e
            )

    def get_spans(
        self, plugin_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get trace spans, optionally filtered by plugin.

        Args:
            plugin_id: Optional plugin identifier to filter by.

        Returns:
            List of span dictionaries.
        """
        spans = list(self._spans.values())
        if plugin_id:
            spans = [s for s in spans if s.get("plugin_id") == plugin_id]
        return sorted(spans, key=lambda s: s["start_time"])

    def get_traces(
        self, plugin_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get traces grouped by trace ID.

        Args:
            plugin_id: Optional plugin identifier to filter by.

        Returns:
            List of trace dictionaries, each containing trace_id
            and its spans.
        """
        spans = list(self._spans.values())
        if plugin_id:
            spans = [s for s in spans if s.get("plugin_id") == plugin_id]

        traces: Dict[str, List[Dict[str, Any]]] = {}
        for span in spans:
            tid = span["trace_id"]
            traces.setdefault(tid, []).append(span)

        result: List[Dict[str, Any]] = []
        for trace_id, trace_spans in traces.items():
            result.append({
                "trace_id": trace_id,
                "spans": sorted(
                    trace_spans, key=lambda s: s["start_time"]
                ),
                "span_count": len(trace_spans),
                "plugin_ids": list(
                    {s["plugin_id"] for s in trace_spans if s.get("plugin_id")}
                ),
            })
        return result

    def get_audit_trail(
        self, plugin_id: str
    ) -> List[Dict[str, Any]]:
        """Get the audit trail for a specific plugin.

        Args:
            plugin_id: The plugin identifier.

        Returns:
            List of audit entries in chronological order.
        """
        return list(self._audit.get(plugin_id, []))

    def get_stats(self) -> Dict[str, Any]:
        """Get telemetry statistics.

        Returns:
            Dictionary with event counts, span counts, trace counts,
            and audit trail sizes.
        """
        return {
            "total_events": self._event_count,
            "total_spans": self._span_count,
            "active_spans": sum(
                1 for s in self._spans.values() if s["status"] == "active"
            ),
            "completed_spans": sum(
                1 for s in self._spans.values() if s["status"] != "active"
            ),
            "total_traces": len(self._traces),
            "traced_plugins": sorted(
                {s["plugin_id"] for s in self._spans.values() if s.get("plugin_id")}
            ),
            "audit_plugins": sorted(self._audit.keys()),
            "events_in_memory": len(self._events),
            "spans_in_memory": len(self._spans),
        }