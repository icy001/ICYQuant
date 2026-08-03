"""
Telemetry service.

Unified telemetry management for metrics,
traces, logs, and events across the
ICYQuant platform.

Provides a single interface for recording
all observability data, enabling correlation
between metrics, traces, and logs.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from .models import MetricPoint


class TelemetryService:
    """
    Unified telemetry service.

    Manages four telemetry pillars:
    - Metrics: Numeric measurements
    - Traces: Distributed tracing spans
    - Logs: Structured log events
    - Events: Business/domain events

    Usage:
        telemetry = TelemetryService()

        await telemetry.record_metric(
            MetricPoint(name="requests", value=100)
        )

        span = telemetry.start_span("database_query")
        # ... do work ...
        telemetry.end_span(span)

        await telemetry.record_log(
            level="info",
            message="Database query completed",
        )
    """

    def __init__(
        self,
        max_history: int = 10000,
    ) -> None:
        """
        Initialize telemetry service.

        Args:
            max_history: Maximum records to keep per pillar.
        """

        self._max_history = max_history
        self._metrics: List[MetricPoint] = []
        self._traces: List[Dict[str, Any]] = []
        self._logs: List[Dict[str, Any]] = []
        self._events: List[Dict[str, Any]] = []

        self._metric_counts: Dict[str, int] = defaultdict(int)
        self._trace_count: int = 0
        self._log_count: int = 0
        self._event_count: int = 0

    # === Metrics ===

    async def record_metric(
        self,
        metric: MetricPoint,
    ) -> None:
        """
        Record a metric data point.

        Args:
            metric: MetricPoint to record.
        """

        self._metrics.append(metric)
        self._metric_counts[metric.name] += 1

        if len(self._metrics) > self._max_history:
            self._metrics = self._metrics[-self._max_history:]

    async def record_metrics(
        self,
        metrics: List[MetricPoint],
    ) -> None:
        """
        Record multiple metric data points.

        Args:
            metrics: List of MetricPoints.
        """

        for m in metrics:
            await self.record_metric(m)

    # === Traces ===

    def start_span(
        self,
        name: str,
        parent_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Start a tracing span.

        Args:
            name: Span name.
            parent_id: Parent span ID.
            attributes: Span attributes.

        Returns:
            Span dictionary.
        """

        import uuid

        span = {
            "id": str(uuid.uuid4()),
            "name": name,
            "parent_id": parent_id,
            "start_time": time.time(),
            "end_time": None,
            "duration": None,
            "attributes": attributes or {},
            "status": "active",
        }
        return span

    def end_span(
        self,
        span: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        End a tracing span.

        Args:
            span: Span dictionary.

        Returns:
            Completed span dictionary.
        """

        span["end_time"] = time.time()
        span["duration"] = (
            span["end_time"] - span["start_time"]
        )
        span["status"] = "completed"

        self._traces.append(span)
        self._trace_count += 1

        if len(self._traces) > self._max_history:
            self._traces = self._traces[-self._max_history:]

        return span

    async def record_trace(
        self,
        trace: Dict[str, Any],
    ) -> None:
        """
        Record a completed trace span.

        Args:
            trace: Trace span dictionary.
        """

        self._traces.append(trace)
        self._trace_count += 1

        if len(self._traces) > self._max_history:
            self._traces = self._traces[-self._max_history:]

    # === Logs ===

    async def record_log(
        self,
        level: str = "info",
        message: str = "",
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record a structured log entry.

        Args:
            level: Log level (debug, info, warning, error, critical).
            message: Log message.
            attributes: Additional log attributes.
        """

        entry = {
            "timestamp": time.time(),
            "level": level,
            "message": message,
            "attributes": attributes or {},
        }

        self._logs.append(entry)
        self._log_count += 1

        if len(self._logs) > self._max_history:
            self._logs = self._logs[-self._max_history:]

    # === Events ===

    async def record_event(
        self,
        event_type: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record a business/domain event.

        Args:
            event_type: Event type name.
            data: Event payload.
        """

        event = {
            "timestamp": time.time(),
            "type": event_type,
            "data": data or {},
        }

        self._events.append(event)
        self._event_count += 1

        if len(self._events) > self._max_history:
            self._events = self._events[-self._max_history:]

    # === Query ===

    def get_recent_metrics(
        self,
        count: int = 100,
    ) -> List[MetricPoint]:
        """
        Get recent metrics.

        Args:
            count: Number of recent metrics.

        Returns:
            List of recent MetricPoints.
        """

        return self._metrics[-count:]

    def get_recent_traces(
        self,
        count: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get recent traces.

        Args:
            count: Number of recent traces.

        Returns:
            List of recent trace spans.
        """

        return self._traces[-count:]

    def get_recent_logs(
        self,
        count: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get recent logs.

        Args:
            count: Number of recent logs.

        Returns:
            List of recent log entries.
        """

        return self._logs[-count:]

    def get_recent_events(
        self,
        count: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get recent events.

        Args:
            count: Number of recent events.

        Returns:
            List of recent events.
        """

        return self._events[-count:]

    # === Status ===

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """
        Get telemetry service status.

        Returns:
            Status dictionary.
        """

        return {
            "metrics_recorded": len(self._metrics),
            "unique_metrics": len(self._metric_counts),
            "traces_recorded": self._trace_count,
            "logs_recorded": self._log_count,
            "events_recorded": self._event_count,
            "max_history": self._max_history,
        }

    def clear(
        self,
    ) -> None:
        """Clear all telemetry data."""

        self._metrics.clear()
        self._traces.clear()
        self._logs.clear()
        self._events.clear()
        self._metric_counts.clear()
        self._trace_count = 0
        self._log_count = 0
        self._event_count = 0
