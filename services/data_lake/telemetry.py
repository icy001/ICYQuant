"""
Data Lake Telemetry — Distributed tracing for the data lake covering
ingestion, storage, query, replay, and snapshot timelines.

Commit 16 Part 1.3
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class DataLakeSpan:
    """A telemetry span within a data lake operation trace."""
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
class DataLakeTrace:
    """A complete telemetry trace for a data lake operation."""
    trace_id: str
    operation: str
    spans: list[DataLakeSpan] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    status: str = "running"


class DataLakeTelemetry:
    """
    Distributed telemetry for the enterprise historical data lake.

    Provides end-to-end tracing across all data lake pipelines:
        Ingestion Pipeline → Storage Pipeline → Query Pipeline
        → Replay Pipeline → Snapshot Pipeline → Lifecycle Pipeline

    Categories:
        - ingestion: data ingestion from market data sources
        - storage: write, read, compaction operations
        - query: historical and time-travel queries
        - replay: market data replay sessions
        - snapshot: dataset snapshots
        - lifecycle: retention, cleanup, lifecycle transitions

    Usage::

        telemetry = DataLakeTelemetry()
        await telemetry.initialize()

        trace = telemetry.start_trace("ingest_us_equity", "ingestion")
        span = telemetry.start_span(trace.trace_id, "write_parquet", "storage")
        telemetry.end_span(span.span_id)
        telemetry.end_trace(trace.trace_id)
    """

    CATEGORY_INGESTION = "ingestion"
    CATEGORY_STORAGE = "storage"
    CATEGORY_QUERY = "query"
    CATEGORY_REPLAY = "replay"
    CATEGORY_SNAPSHOT = "snapshot"
    CATEGORY_LIFECYCLE = "lifecycle"
    CATEGORY_COMPACTION = "compaction"
    CATEGORY_SCHEMA = "schema"

    def __init__(self, max_traces: int = 10000) -> None:
        self._traces: dict[str, DataLakeTrace] = {}
        self._spans: dict[str, DataLakeSpan] = {}
        self._max_traces = max_traces

    async def initialize(self) -> None:
        """Initialize the telemetry system."""
        logger.info("DataLakeTelemetry initialized.")

    async def stop(self) -> None:
        """Stop the telemetry system."""
        self._traces.clear()
        self._spans.clear()
        logger.info("DataLakeTelemetry stopped.")

    # ── Trace Operations ──────────────────────────────────────────

    def start_trace(self, name: str, operation: str = "generic") -> DataLakeTrace:
        """Start a new telemetry trace."""
        trace_id = str(uuid.uuid4())
        trace = DataLakeTrace(trace_id=trace_id, operation=operation)
        self._traces[trace_id] = trace

        # Enforce max trace limit
        if len(self._traces) > self._max_traces:
            oldest = next(iter(self._traces.keys()))
            del self._traces[oldest]

        logger.debug("Trace started: %s [%s]", name, trace_id[:8])
        return trace

    def end_trace(
        self, trace_id: str, status: str = "completed"
    ) -> Optional[DataLakeTrace]:
        """End a telemetry trace."""
        trace = self._traces.get(trace_id)
        if trace:
            trace.completed_at = datetime.now(timezone.utc)
            trace.status = status
            total_ms = sum(s.duration_ms for s in trace.spans)
            logger.debug(
                "Trace %s completed: %d spans, %.2fms, status=%s",
                trace_id[:8], len(trace.spans), total_ms, status,
            )
        return trace

    # ── Span Operations ───────────────────────────────────────────

    def start_span(
        self,
        trace_id: str,
        name: str,
        category: str,
        parent_span_id: Optional[str] = None,
        tags: Optional[dict[str, str]] = None,
    ) -> Optional[DataLakeSpan]:
        """Start a new span within a trace."""
        trace = self._traces.get(trace_id)
        if trace is None:
            logger.warning("Span requested for unknown trace: %s", trace_id)
            return None

        span_id = str(uuid.uuid4())
        span = DataLakeSpan(
            span_id=span_id,
            trace_id=trace_id,
            name=name,
            category=category,
            parent_span_id=parent_span_id,
            tags=tags or {},
        )
        self._spans[span_id] = span
        trace.spans.append(span)

        if len(self._spans) > self._max_traces * 10:
            oldest = next(iter(self._spans.keys()))
            del self._spans[oldest]

        return span

    def end_span(
        self,
        span_id: str,
        status: str = "ok",
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[DataLakeSpan]:
        """End a span."""
        span = self._spans.get(span_id)
        if span:
            span.ended_at = time.monotonic()
            span.duration_ms = (span.ended_at - span.started_at) * 1000
            span.status = status
            if metadata:
                span.metadata.update(metadata)
        return span

    # ── Convenience Tracing Methods ───────────────────────────────

    def trace_ingestion(
        self, dataset: str, source: str
    ) -> tuple[DataLakeTrace, DataLakeSpan]:
        """Start an ingestion trace with initial span."""
        trace = self.start_trace(f"ingest_{dataset}", self.CATEGORY_INGESTION)
        span = self.start_span(
            trace.trace_id,
            f"receive_from_{source}",
            self.CATEGORY_INGESTION,
            tags={"dataset": dataset, "source": source},
        )
        return trace, span

    def trace_query(
        self, dataset: str, query_type: str = "historical"
    ) -> tuple[DataLakeTrace, DataLakeSpan]:
        """Start a query trace with initial span."""
        trace = self.start_trace(f"query_{dataset}", self.CATEGORY_QUERY)
        span = self.start_span(
            trace.trace_id,
            f"{query_type}_query",
            self.CATEGORY_QUERY,
            tags={"dataset": dataset, "query_type": query_type},
        )
        return trace, span

    def trace_replay(
        self, dataset: str, start_time: str, end_time: str
    ) -> tuple[DataLakeTrace, DataLakeSpan]:
        """Start a replay trace with initial span."""
        trace = self.start_trace(f"replay_{dataset}", self.CATEGORY_REPLAY)
        span = self.start_span(
            trace.trace_id,
            "replay_session",
            self.CATEGORY_REPLAY,
            tags={
                "dataset": dataset,
                "start_time": start_time,
                "end_time": end_time,
            },
        )
        return trace, span

    def trace_snapshot(
        self, dataset: str, version_id: str
    ) -> tuple[DataLakeTrace, DataLakeSpan]:
        """Start a snapshot trace with initial span."""
        trace = self.start_trace(f"snapshot_{dataset}", self.CATEGORY_SNAPSHOT)
        span = self.start_span(
            trace.trace_id,
            "create_snapshot",
            self.CATEGORY_SNAPSHOT,
            tags={"dataset": dataset, "version_id": version_id},
        )
        return trace, span

    # ── Queries ───────────────────────────────────────────────────

    def get_trace(self, trace_id: str) -> Optional[DataLakeTrace]:
        """Get a trace by ID."""
        return self._traces.get(trace_id)

    def get_span(self, span_id: str) -> Optional[DataLakeSpan]:
        """Get a span by ID."""
        return self._spans.get(span_id)

    def get_timeline(self, trace_id: str) -> list[dict[str, Any]]:
        """Get a chronological timeline of spans in a trace."""
        trace = self._traces.get(trace_id)
        if trace is None:
            return []

        sorted_spans = sorted(trace.spans, key=lambda s: s.started_at)
        return [
            {
                "span_id": s.span_id,
                "name": s.name,
                "category": s.category,
                "duration_ms": s.duration_ms,
                "status": s.status,
                "tags": s.tags,
            }
            for s in sorted_spans
        ]

    def get_summary(self) -> dict[str, Any]:
        """Get telemetry summary."""
        total_spans = len(self._spans)
        active_traces = sum(
            1 for t in self._traces.values() if t.status == "running"
        )
        completed_traces = sum(
            1 for t in self._traces.values() if t.status == "completed"
        )

        category_counts: dict[str, int] = {}
        category_durations: dict[str, float] = {}
        for s in self._spans.values():
            category_counts[s.category] = category_counts.get(s.category, 0) + 1
            category_durations[s.category] = (
                category_durations.get(s.category, 0.0) + s.duration_ms
            )

        return {
            "total_traces": len(self._traces),
            "active_traces": active_traces,
            "completed_traces": completed_traces,
            "total_spans": total_spans,
            "spans_by_category": category_counts,
            "avg_duration_ms_by_category": {
                cat: round(dur / max(category_counts.get(cat, 1), 1), 2)
                for cat, dur in category_durations.items()
            },
        }
