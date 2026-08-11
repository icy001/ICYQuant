"""
Telemetry — Distributed tracing for the Autonomous Risk & Execution Platform.

Provides end-to-end tracing across the full decision pipeline:
    Risk Timeline → Execution Timeline → Feedback Timeline → Audit Trail

Usage::

    telemetry = Telemetry(max_traces=5000)

    trace = await telemetry.start_trace("portfolio_rebalance", entity_id="book-001")
    span  = await telemetry.start_span(trace.trace_id, "compute_targets", "risk")
    ...
    await telemetry.end_span(span.span_id)
    await telemetry.end_trace(trace.trace_id, status="completed")

    stats = await telemetry.get_stats()
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SpanCategory(Enum):
    """Logical categories for telemetry spans across the risk-execution pipeline."""

    RISK = "risk"
    EXECUTION = "execution"
    PLANNING = "planning"
    FEEDBACK = "feedback"
    AUDIT = "audit"
    POLICY = "policy"


@dataclass
class TelemetrySpan:
    """
    A single unit of work within a trace.

    Represents an atomic operation such as a risk check, an execution step,
    a feedback analysis, a policy evaluation, or an audit record.

    Attributes:
        span_id:   Unique identifier for this span.
        trace_id:  The trace this span belongs to.
        name:      Human-readable operation name (e.g. "check_risk_budget").
        category:  Pipeline stage category (risk, execution, planning, etc.).
        parent_span_id: ID of the parent span for nested operations.
        started_at: Monotonic timestamp when the span began.
        ended_at:   Monotonic timestamp when the span ended.
        duration_ms: Duration of the span in milliseconds.
        status:     Outcome status ("ok", "error", "timeout", etc.).
        tags:      Key-value tags for filtering and grouping.
        metadata:  Arbitrary structured data produced by the operation.
    """

    span_id: str
    trace_id: str
    name: str
    category: str
    parent_span_id: Optional[str] = None
    started_at: float = field(default_factory=time.monotonic)
    ended_at: Optional[float] = None
    duration_ms: float = 0.0
    status: str = "ok"
    tags: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TelemetryTrace:
    """
    A complete end-to-end trace for a pipeline request.

    Groups all spans produced during a single logical flow, such as
    rebalancing a portfolio, executing an order slice, or evaluating
    a policy change.

    Attributes:
        trace_id:   Unique identifier for this trace.
        name:       Human-readable trace name (e.g. "portfolio_rebalance").
        entity_id:  Domain identifier (book, portfolio, order, etc.).
        spans:      Ordered list of child spans.
        started_at: UTC datetime when the trace was created.
        completed_at: UTC datetime when the trace was finished.
        status:     Final status ("running", "completed", "error", etc.).
        tags:       Key-value tags for filtering and grouping.
    """

    trace_id: str
    name: str
    entity_id: str = ""
    spans: list[TelemetrySpan] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    status: str = "running"
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class TelemetryStats:
    """
    Aggregate statistics for the telemetry system.

    Provides a high-level view of tracing activity across the platform,
    useful for dashboards, capacity planning, and anomaly detection.

    Attributes:
        total_traces:      Total number of traces recorded.
        active_traces:     Number of traces that have not yet completed.
        completed_traces:  Number of traces that have finished.
        total_spans:       Total number of spans across all traces.
        by_category:       Span counts grouped by category.
        avg_duration_ms:   Average duration of completed traces in ms.
        p95_duration_ms:   95th percentile duration of completed traces in ms.
    """

    total_traces: int = 0
    active_traces: int = 0
    completed_traces: int = 0
    total_spans: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    avg_duration_ms: float = 0.0
    p95_duration_ms: float = 0.0


class Telemetry:
    """
    Distributed tracing for the Autonomous Risk & Execution Platform.

    Provides end-to-end observability across the full decision pipeline:

        Risk Timeline    → risk checks, budget allocation, exposure sizing
        Execution Timeline → planning, scheduling, slicing, routing
        Feedback Timeline → fill analysis, slippage review, quality scoring
        Audit Trail      → policy evaluation, compliance verification

    Each trace captures the full lifecycle of a request, while spans
    represent individual operations within that lifecycle.  Traces can
    be queried by entity, exported for analysis, and summarised into
    aggregate statistics.

    Usage::

        telemetry = Telemetry(max_traces=5000)

        # --- Risk phase ---
        trace = await telemetry.start_trace("rebalance", entity_id="book-42")
        risk_span = await telemetry.start_span(
            trace.trace_id, "check_portfolio_risk", category="risk"
        )
        await telemetry.end_span(risk_span.span_id, status="ok")

        # --- Execution phase ---
        exec_span = await telemetry.start_span(
            trace.trace_id, "schedule_order_slices", category="execution"
        )
        await telemetry.end_span(exec_span.span_id, status="ok")

        # --- Feedback phase ---
        fb_span = await telemetry.start_span(
            trace.trace_id, "analyse_fill_quality", category="feedback"
        )
        await telemetry.end_span(fb_span.span_id, status="ok")

        # --- Finalise ---
        await telemetry.end_trace(trace.trace_id, status="completed")

        stats = await telemetry.get_stats()
    """

    def __init__(self, max_traces: int = 5000) -> None:
        self._traces: dict[str, TelemetryTrace] = {}
        self._spans: dict[str, TelemetrySpan] = {}
        self._max_traces = max_traces
        logger.info("Telemetry initialised (max_traces=%d).", max_traces)

    # ------------------------------------------------------------------
    # Trace operations
    # ------------------------------------------------------------------

    async def start_trace(self, name: str, entity_id: str = "") -> TelemetryTrace:
        """
        Create and register a new trace.

        Args:
            name:      Human-readable trace name.
            entity_id: Domain identifier (book, portfolio, order, etc.).

        Returns:
            The newly created ``TelemetryTrace``.
        """
        trace_id = str(uuid.uuid4())
        trace = TelemetryTrace(trace_id=trace_id, name=name, entity_id=entity_id)
        self._traces[trace_id] = trace

        if len(self._traces) > self._max_traces:
            oldest_keys = sorted(self._traces.keys())[
                : len(self._traces) - self._max_traces
            ]
            for tid in oldest_keys:
                old_trace = self._traces.pop(tid, None)
                if old_trace is not None:
                    for span in old_trace.spans:
                        self._spans.pop(span.span_id, None)

        logger.debug("Trace started: %s (%s)", trace_id, name)
        return trace

    async def end_trace(self, trace_id: str, status: str = "completed") -> None:
        """
        Finalise a trace with the given status.

        Args:
            trace_id: ID of the trace to finalise.
            status:   Final status string (e.g. "completed", "error").
        """
        trace = self._traces.get(trace_id)
        if trace is None:
            logger.warning("end_trace: trace %s not found.", trace_id)
            return
        trace.completed_at = datetime.now(timezone.utc)
        trace.status = status
        logger.debug("Trace ended: %s (status=%s)", trace_id, status)

    # ------------------------------------------------------------------
    # Span operations
    # ------------------------------------------------------------------

    async def start_span(
        self, trace_id: str, name: str, category: str = "risk"
    ) -> TelemetrySpan:
        """
        Create and register a new span within an existing trace.

        Args:
            trace_id: ID of the parent trace.
            name:     Human-readable operation name.
            category: Pipeline category (see ``SpanCategory``).

        Returns:
            The newly created ``TelemetrySpan``.
        """
        span_id = str(uuid.uuid4())
        span = TelemetrySpan(
            span_id=span_id,
            trace_id=trace_id,
            name=name,
            category=category,
        )
        self._spans[span_id] = span

        trace = self._traces.get(trace_id)
        if trace is not None:
            trace.spans.append(span)
        else:
            logger.warning(
                "start_span: trace %s not found; span %s orphaned.", trace_id, span_id
            )

        logger.debug("Span started: %s (%s) [%s]", span_id, name, category)
        return span

    async def end_span(self, span_id: str, status: str = "ok") -> None:
        """
        Finalise a span with the given status.

        Computes the span duration automatically from the monotonic clock.

        Args:
            span_id: ID of the span to finalise.
            status:  Outcome status (e.g. "ok", "error", "timeout").
        """
        span = self._spans.get(span_id)
        if span is None:
            logger.warning("end_span: span %s not found.", span_id)
            return
        span.ended_at = time.monotonic()
        span.duration_ms = (span.ended_at - span.started_at) * 1000
        span.status = status
        logger.debug(
            "Span ended: %s (status=%s, duration=%.2fms)",
            span_id,
            status,
            span.duration_ms,
        )

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    async def get_trace(self, trace_id: str) -> TelemetryTrace:
        """
        Retrieve a trace by its ID.

        Args:
            trace_id: The trace identifier.

        Returns:
            The matching ``TelemetryTrace``, or ``None`` if not found.
        """
        return self._traces.get(trace_id)

    async def get_entity_traces(
        self, entity_id: str, limit: int = 20
    ) -> list[TelemetryTrace]:
        """
        Retrieve the most recent traces for a given entity.

        Args:
            entity_id: The domain identifier (book, portfolio, order, etc.).
            limit:     Maximum number of traces to return (newest first).

        Returns:
            A list of ``TelemetryTrace`` objects matching the entity,
            ordered by most recently started.
        """
        matching = [
            t
            for t in self._traces.values()
            if t.entity_id == entity_id
        ]
        matching.sort(key=lambda t: t.started_at, reverse=True)
        return matching[:limit]

    async def get_active_traces(self) -> list[TelemetryTrace]:
        """
        Retrieve all traces that are still running (not yet finalised).

        Returns:
            A list of active ``TelemetryTrace`` objects.
        """
        return [t for t in self._traces.values() if t.status == "running"]

    # ------------------------------------------------------------------
    # Export & analytics
    # ------------------------------------------------------------------

    async def export_traces(self, format: str = "json") -> str:
        """
        Export all traces in the requested format.

        Args:
            format: Export format. Currently only ``"json"`` is supported.

        Returns:
            Serialised trace data as a string.

        Raises:
            ValueError: If the requested format is not supported.
        """
        if format != "json":
            raise ValueError(f"Unsupported export format: {format}")

        payload = []
        for trace in self._traces.values():
            trace_data: dict[str, Any] = {
                "trace_id": trace.trace_id,
                "name": trace.name,
                "entity_id": trace.entity_id,
                "status": trace.status,
                "started_at": trace.started_at.isoformat(),
                "completed_at": (
                    trace.completed_at.isoformat() if trace.completed_at else None
                ),
                "tags": trace.tags,
                "spans": [
                    {
                        "span_id": s.span_id,
                        "trace_id": s.trace_id,
                        "name": s.name,
                        "category": s.category,
                        "parent_span_id": s.parent_span_id,
                        "started_at": s.started_at,
                        "ended_at": s.ended_at,
                        "duration_ms": s.duration_ms,
                        "status": s.status,
                        "tags": s.tags,
                        "metadata": s.metadata,
                    }
                    for s in trace.spans
                ],
            }
            payload.append(trace_data)

        return json.dumps(payload, indent=2, default=str)

    async def get_stats(self) -> TelemetryStats:
        """
        Compute aggregate statistics across all traces and spans.

        Returns:
            A ``TelemetryStats`` instance summarising the current state
            of the telemetry system, including counts, category breakdown,
            and duration percentiles for completed traces.
        """
        traces = list(self._traces.values())
        total_traces = len(traces)
        active_traces = sum(1 for t in traces if t.status == "running")
        completed_traces = sum(1 for t in traces if t.status != "running")

        all_spans = list(self._spans.values())
        total_spans = len(all_spans)

        by_category: dict[str, int] = {}
        for span in all_spans:
            cat = span.category
            by_category[cat] = by_category.get(cat, 0) + 1

        completed_durations = [
            (t.completed_at - t.started_at).total_seconds() * 1000
            for t in traces
            if t.completed_at is not None
        ]

        avg_duration_ms = 0.0
        p95_duration_ms = 0.0
        if completed_durations:
            sorted_durations = sorted(completed_durations)
            avg_duration_ms = sum(sorted_durations) / len(sorted_durations)
            idx = int(len(sorted_durations) * 0.95)
            p95_duration_ms = sorted_durations[min(idx, len(sorted_durations) - 1)]

        return TelemetryStats(
            total_traces=total_traces,
            active_traces=active_traces,
            completed_traces=completed_traces,
            total_spans=total_spans,
            by_category=by_category,
            avg_duration_ms=avg_duration_ms,
            p95_duration_ms=p95_duration_ms,
        )