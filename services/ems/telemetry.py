"""EMS Telemetry — Distributed tracing for the Execution Management System.

Provides distributed tracing spans for execution operations, enabling
end-to-end visibility into execution performance and latency.

Span Types:
    - execution: Overall execution span
    - algorithm: Algorithm decision-making span
    - child_order: Child order lifecycle span
    - fill: Fill event span
    - quality: Quality analysis span

Usage::

    telemetry = EMSTelemetry()
    with telemetry.trace_execution(task_id, strategy):
        await engine.start(plan)
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Generator, Optional

logger = logging.getLogger(__name__)


@dataclass
class Span:
    """A distributed tracing span.

    Attributes:
        span_id: Unique span identifier
        trace_id: Trace identifier (shared across spans)
        parent_id: Parent span identifier
        name: Span operation name
        service: Service name
        start_time: Span start time
        end_time: Span end time
        duration_ms: Span duration in milliseconds
        tags: Key-value tags
        status: Span status (ok/error)
    """

    span_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""
    parent_id: str = ""
    name: str = ""
    service: str = "ems"
    start_time: float = field(default_factory=time.monotonic)
    end_time: float = 0.0
    duration_ms: float = 0.0
    tags: dict[str, Any] = field(default_factory=dict)
    status: str = "ok"

    def finish(self) -> None:
        """Complete the span."""
        self.end_time = time.monotonic()
        self.duration_ms = (self.end_time - self.start_time) * 1000

    def set_tag(self, key: str, value: Any) -> None:
        """Set a span tag.

        Args:
            key: Tag key
            value: Tag value
        """
        self.tags[key] = value

    def set_error(self, error: str) -> None:
        """Mark span as error.

        Args:
            error: Error message
        """
        self.status = "error"
        self.tags["error"] = error

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "service": self.service,
            "duration_ms": self.duration_ms,
            "tags": self.tags,
            "status": self.status,
        }


class EMSTelemetry:
    """EMS distributed tracing provider.

    Manages span creation and tracking for execution operations.
    Provides context managers for automatic span lifecycle management.

    Attributes:
        _spans: Active spans
        _completed_spans: Finished spans for reporting
    """

    def __init__(self) -> None:
        self._spans: dict[str, Span] = {}
        self._completed_spans: list[Span] = []
        self._trace_counter: int = 0

    # ── Span Creation ──────────────────────────────────────────────

    @contextmanager
    def trace_execution(self, task_id: str, strategy: str) -> Generator[Span, None, None]:
        """Create an execution span.

        Traces the full execution lifecycle from start to completion.

        Args:
            task_id: Execution task identifier
            strategy: Algorithm strategy name

        Yields:
            Span for the execution
        """
        trace_id = self._generate_trace_id()
        span = Span(
            trace_id=trace_id,
            name=f"execution.{strategy}",
            tags={
                "task_id": task_id,
                "strategy": strategy,
                "span.kind": "execution",
            },
        )
        self._spans[span.span_id] = span

        try:
            yield span
        except Exception as e:
            span.set_error(str(e))
            raise
        finally:
            span.finish()
            self._completed_spans.append(span)
            self._spans.pop(span.span_id, None)

            logger.debug(
                "Execution span: task=%s strategy=%s duration=%.1fms status=%s",
                task_id,
                strategy,
                span.duration_ms,
                span.status,
            )

    @contextmanager
    def trace_algorithm(self, task_id: str, strategy: str) -> Generator[Span, None, None]:
        """Create an algorithm decision span.

        Traces algorithm decision-making and child order generation.

        Args:
            task_id: Execution task identifier
            strategy: Algorithm name

        Yields:
            Span for algorithm operations
        """
        trace_id = self._generate_trace_id()
        span = Span(
            trace_id=trace_id,
            name=f"algorithm.{strategy}",
            tags={
                "task_id": task_id,
                "strategy": strategy,
                "span.kind": "algorithm",
            },
        )
        self._spans[span.span_id] = span

        try:
            yield span
        except Exception as e:
            span.set_error(str(e))
            raise
        finally:
            span.finish()
            self._completed_spans.append(span)
            self._spans.pop(span.span_id, None)

    @contextmanager
    def trace_child_order(self, task_id: str, child_order_id: str) -> Generator[Span, None, None]:
        """Create a child order lifecycle span.

        Traces a child order from dispatch to fill.

        Args:
            task_id: Execution task identifier
            child_order_id: Child order identifier

        Yields:
            Span for child order operations
        """
        trace_id = self._generate_trace_id()
        span = Span(
            trace_id=trace_id,
            name="child_order",
            tags={
                "task_id": task_id,
                "child_order_id": child_order_id,
                "span.kind": "child_order",
            },
        )
        self._spans[span.span_id] = span

        try:
            yield span
        except Exception as e:
            span.set_error(str(e))
            raise
        finally:
            span.finish()
            self._completed_spans.append(span)
            self._spans.pop(span.span_id, None)

    @contextmanager
    def trace_fill(self, task_id: str, child_order_id: str) -> Generator[Span, None, None]:
        """Create a fill event span.

        Traces a fill event from receipt to processing.

        Args:
            task_id: Execution task identifier
            child_order_id: Child order identifier

        Yields:
            Span for fill operations
        """
        trace_id = self._generate_trace_id()
        span = Span(
            trace_id=trace_id,
            name="fill",
            tags={
                "task_id": task_id,
                "child_order_id": child_order_id,
                "span.kind": "fill",
            },
        )
        self._spans[span.span_id] = span

        try:
            yield span
        except Exception as e:
            span.set_error(str(e))
            raise
        finally:
            span.finish()
            self._completed_spans.append(span)
            self._spans.pop(span.span_id, None)

    @contextmanager
    def trace_quality(self, task_id: str) -> Generator[Span, None, None]:
        """Create a quality analysis span.

        Traces execution quality computation.

        Args:
            task_id: Execution task identifier

        Yields:
            Span for quality operations
        """
        trace_id = self._generate_trace_id()
        span = Span(
            trace_id=trace_id,
            name="quality",
            tags={
                "task_id": task_id,
                "span.kind": "quality",
            },
        )
        self._spans[span.span_id] = span

        try:
            yield span
        except Exception as e:
            span.set_error(str(e))
            raise
        finally:
            span.finish()
            self._completed_spans.append(span)
            self._spans.pop(span.span_id, None)

    # ── Query API ──────────────────────────────────────────────────

    def get_completed_spans(self) -> list[Span]:
        """Get all completed spans.

        Returns:
            List of completed Span objects
        """
        return list(self._completed_spans)

    def get_active_spans(self) -> list[Span]:
        """Get all active spans.

        Returns:
            List of active Span objects
        """
        return list(self._spans.values())

    def get_span_count(self) -> int:
        """Get total completed span count.

        Returns:
            Number of completed spans
        """
        return len(self._completed_spans)

    def clear(self) -> None:
        """Clear all completed spans."""
        self._completed_spans.clear()

    # ── Helpers ────────────────────────────────────────────────────

    def _generate_trace_id(self) -> str:
        """Generate a unique trace ID."""
        self._trace_counter += 1
        return f"trace_{self._trace_counter}_{uuid.uuid4().hex[:8]}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize telemetry state."""
        return {
            "active_spans": len(self._spans),
            "completed_spans": len(self._completed_spans),
            "recent_spans": [s.to_dict() for s in self._completed_spans[-10:]],
        }
