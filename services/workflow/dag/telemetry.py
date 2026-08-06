"""
DAG Telemetry — unified observability for DAG execution.

Provides:
- Tracing: DAG compilation, scheduling, and execution timelines
- Logging: Structured logs for each phase
- Metrics: Automatic metric recording
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.workflow.dag.metrics import DAGMetricsCollector

logger = logging.getLogger(__name__)


@dataclass
class Span:
    """A telemetry span representing a unit of work."""

    name: str
    start_time: float = 0.0
    end_time: float = 0.0
    tags: Dict[str, str] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000


class DAGTelemetry:
    """
    Provides unified telemetry for DAG operations.

    Integrates tracing, logging, and metrics into a single interface.
    """

    def __init__(self, metrics: Optional[DAGMetricsCollector] = None):
        self.metrics = metrics or DAGMetricsCollector()
        self._active_spans: Dict[str, Span] = {}
        self._completed_spans: List[Span] = []

    @asynccontextmanager
    async def trace(self, name: str, **tags):
        """
        Context manager for tracing a DAG operation.

        Usage:
            async with telemetry.trace("dag.compile", workflow_id="wf_123"):
                await compiler.compile(workflow)
        """
        span = Span(name=name, start_time=time.monotonic(), tags=tags)
        span_id = f"{name}_{id(span)}"
        self._active_spans[span_id] = span

        logger.debug(f"Span started: {name}", extra=tags)

        try:
            yield span
        except Exception as e:
            span.events.append({"type": "error", "error": str(e)})
            logger.error(f"Span failed: {name}: {e}", extra=tags)
            raise
        finally:
            span.end_time = time.monotonic()
            self._completed_spans.append(span)
            self._active_spans.pop(span_id, None)
            logger.debug(
                f"Span completed: {name} ({span.duration_ms:.2f}ms)",
                extra=tags,
            )

    def log_event(self, event_type: str, **data) -> None:
        """Log a structured event."""
        logger.info(f"DAG Event: {event_type}", extra=data)

    def log_metric(self, metric_name: str, value: float) -> None:
        """Record a metric."""
        self.metrics.observe(metric_name, value)

    def get_trace_summary(self) -> Dict[str, Any]:
        """Get a summary of all completed spans."""
        return {
            "total_spans": len(self._completed_spans),
            "active_spans": len(self._active_spans),
            "spans": [
                {
                    "name": s.name,
                    "duration_ms": s.duration_ms,
                    "tags": s.tags,
                }
                for s in self._completed_spans[-20:]  # Last 20 spans
            ],
        }
