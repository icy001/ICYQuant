"""
Monitoring tracing.

Provides tracing hooks around the
monitoring collection and export pipeline,
enabling performance analysis and
distributed tracing of monitoring operations.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


class MonitoringTracing:
    """
    Monitoring operation tracer.

    Wraps collection and export operations
    with tracing spans, recording duration
    and context for performance analysis.

    Hooks:
    - before_collect / after_collect
    - before_export / after_export
    - before_alert / after_alert

    Usage:
        tracer = MonitoringTracing()

        await tracer.before_collect()
        metrics = await collector.collect_all()
        await tracer.after_collect(metrics)
    """

    def __init__(
        self,
        max_spans: int = 1000,
    ) -> None:
        """
        Initialize tracer.

        Args:
            max_spans: Maximum spans to retain.
        """

        self._max_spans = max_spans
        self._spans: List[Dict[str, Any]] = []
        self._active_spans: Dict[str, Dict[str, Any]] = {}

        self._collect_count: int = 0
        self._export_count: int = 0
        self._alert_count: int = 0
        self._total_collect_time: float = 0.0
        self._total_export_time: float = 0.0

    def _start_span(
        self,
        name: str,
        operation: str,
    ) -> str:
        """
        Start a tracing span.

        Args:
            name: Span name.
            operation: Operation type.

        Returns:
            Span ID.
        """

        import uuid

        span_id = str(uuid.uuid4())
        span = {
            "id": span_id,
            "name": name,
            "operation": operation,
            "start_time": time.time(),
            "end_time": None,
            "duration": None,
            "attributes": {},
            "status": "active",
        }
        self._active_spans[span_id] = span
        return span_id

    def _end_span(
        self,
        span_id: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        End a tracing span.

        Args:
            span_id: Span ID.
            attributes: Additional span attributes.

        Returns:
            Completed span dictionary.
        """

        span = self._active_spans.pop(span_id, None)
        if span is None:
            return {}

        span["end_time"] = time.time()
        span["duration"] = (
            span["end_time"] - span["start_time"]
        )
        span["status"] = "completed"

        if attributes:
            span["attributes"].update(attributes)

        self._spans.append(span)
        if len(self._spans) > self._max_spans:
            self._spans = self._spans[-self._max_spans:]

        return span

    # === Collection Tracing ===

    async def before_collect(
        self,
    ) -> str:
        """
        Called before metric collection.

        Returns:
            Span ID for correlation.
        """

        span_id = self._start_span(
            name="collect",
            operation="collect",
        )
        return span_id

    async def after_collect(
        self,
        span_id: str,
        metric_count: int = 0,
    ) -> None:
        """
        Called after metric collection.

        Args:
            span_id: Span ID from before_collect.
            metric_count: Number of metrics collected.
        """

        span = self._end_span(
            span_id,
            attributes={"metric_count": metric_count},
        )

        if span:
            self._collect_count += 1
            self._total_collect_time += span.get(
                "duration", 0.0
            )

    # === Export Tracing ===

    async def before_export(
        self,
    ) -> str:
        """
        Called before metric export.

        Returns:
            Span ID for correlation.
        """

        span_id = self._start_span(
            name="export",
            operation="export",
        )
        return span_id

    async def after_export(
        self,
        span_id: str,
        success: bool = True,
    ) -> None:
        """
        Called after metric export.

        Args:
            span_id: Span ID from before_export.
            success: Whether export succeeded.
        """

        span = self._end_span(
            span_id,
            attributes={"success": success},
        )

        if span:
            self._export_count += 1
            self._total_export_time += span.get(
                "duration", 0.0
            )

    # === Alert Tracing ===

    async def before_alert(
        self,
    ) -> str:
        """
        Called before alert processing.

        Returns:
            Span ID for correlation.
        """

        return self._start_span(
            name="alert",
            operation="alert",
        )

    async def after_alert(
        self,
        span_id: str,
        fired_count: int = 0,
    ) -> None:
        """
        Called after alert processing.

        Args:
            span_id: Span ID from before_alert.
            fired_count: Number of alerts fired.
        """

        span = self._end_span(
            span_id,
            attributes={"fired_count": fired_count},
        )

        if span:
            self._alert_count += 1

    # === Query ===

    @property
    def avg_collect_time(
        self,
    ) -> float:
        """Get average collection time."""

        if self._collect_count == 0:
            return 0.0
        return (
            self._total_collect_time / self._collect_count
        )

    @property
    def avg_export_time(
        self,
    ) -> float:
        """Get average export time."""

        if self._export_count == 0:
            return 0.0
        return (
            self._total_export_time / self._export_count
        )

    def get_recent_spans(
        self,
        count: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get recent tracing spans.

        Args:
            count: Number of spans.

        Returns:
            List of span dictionaries.
        """

        return self._spans[-count:]

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """
        Get tracer status.

        Returns:
            Status dictionary.
        """

        return {
            "total_spans": len(self._spans),
            "active_spans": len(self._active_spans),
            "collect_count": self._collect_count,
            "export_count": self._export_count,
            "alert_count": self._alert_count,
            "avg_collect_time": round(
                self.avg_collect_time, 4
            ),
            "avg_export_time": round(
                self.avg_export_time, 4
            ),
        }

    def clear(
        self,
    ) -> None:
        """Clear all tracing data."""

        self._spans.clear()
        self._active_spans.clear()
        self._collect_count = 0
        self._export_count = 0
        self._alert_count = 0
        self._total_collect_time = 0.0
        self._total_export_time = 0.0
