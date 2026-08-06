"""Distributed trace collector for ICYQuant Service Mesh.

Provides ``Trace``, ``TraceCollector``, and ``TraceTreeBuilder``
for collecting distributed traces across request, RPC, Kafka,
database, and Redis operations.
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from .span_processor import Span, SpanKind, SpanProcessor
from .trace_context import TraceContext, TraceContextManager

logger = logging.getLogger(__name__)


class Trace:
    """A complete distributed trace."""

    def __init__(
        self,
        trace_id: str = "",
        operation: str = "",
        source: str = "",
        destination: str = "",
    ) -> None:
        self.trace_id = trace_id or uuid.uuid4().hex
        self.operation = operation
        self.source = source
        self.destination = destination
        self.spans: List[Span] = []
        self.start_time = datetime.utcnow()
        self.end_time: Optional[datetime] = None
        self.duration_s: float = 0.0
        self.success: bool = True
        self.error: Optional[str] = None
        self._lock = threading.Lock()

    def add_span(self, span: Span) -> None:
        with self._lock:
            self.spans.append(span)

    def finish(self, success: bool = True, error: Optional[str] = None) -> None:
        with self._lock:
            self.end_time = datetime.utcnow()
            delta = self.end_time - self.start_time
            self.duration_s = delta.total_seconds()
            self.success = success
            self.error = error

    @property
    def span_count(self) -> int:
        with self._lock:
            return len(self.spans)

    @property
    def is_completed(self) -> bool:
        return self.end_time is not None

    def get_root_span(self) -> Optional[Span]:
        with self._lock:
            for span in self.spans:
                if not span.parent_span_id:
                    return span
            return self.spans[0] if self.spans else None

    def build_span_tree(self) -> Dict[str, Any]:
        """Build a tree structure from spans."""
        with self._lock:
            spans_by_id = {s.span_id: s for s in self.spans}
            roots: List[Dict[str, Any]] = []
            for span in self.spans:
                parent = spans_by_id.get(span.parent_span_id)
                if parent is None:
                    roots.append(self._build_node(span, spans_by_id))
            return {
                "trace_id": self.trace_id,
                "operation": self.operation,
                "source": self.source,
                "destination": self.destination,
                "start_time": self.start_time.isoformat(),
                "end_time": self.end_time.isoformat() if self.end_time else None,
                "duration_s": self.duration_s,
                "success": self.success,
                "error": self.error,
                "span_count": len(self.spans),
                "roots": roots,
            }

    def _build_node(
        self,
        span: Span,
        spans_by_id: Dict[str, Span],
    ) -> Dict[str, Any]:
        children = [
            self._build_node(s, spans_by_id)
            for s in self.spans
            if s.parent_span_id == span.span_id
        ]
        return {
            "span_id": span.span_id,
            "operation": span.operation,
            "kind": span.kind.value,
            "status": span.status.value,
            "duration_s": span.duration_s,
            "tags": dict(span.tags),
            "children": children,
        }

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "trace_id": self.trace_id,
                "operation": self.operation,
                "source": self.source,
                "destination": self.destination,
                "start_time": self.start_time.isoformat(),
                "end_time": self.end_time.isoformat() if self.end_time else None,
                "duration_s": self.duration_s,
                "success": self.success,
                "error": self.error,
                "span_count": len(self.spans),
                "spans": [s.to_dict() for s in self.spans],
            }


class TraceCollector:
    """Collects distributed traces across the mesh."""

    def __init__(
        self,
        span_processor: Optional[SpanProcessor] = None,
        max_traces: int = 10000,
    ) -> None:
        self._span_processor = span_processor or SpanProcessor()
        self._max_traces = max_traces
        self._lock = threading.RLock()
        self._traces: Dict[str, Trace] = {}
        self._completed: List[Trace] = []
        self._max_completed = 5000
        self._trace_count = 0
        self._started = False

    @property
    def span_processor(self) -> SpanProcessor:
        return self._span_processor

    @property
    def is_running(self) -> bool:
        return self._started

    def start(self) -> None:
        self._started = True
        logger.info("Trace collector started")

    def stop(self) -> None:
        self._started = False
        logger.info("Trace collector stopped")

    def start_trace(
        self,
        operation: str = "",
        source: str = "",
        destination: str = "",
        baggage: Optional[Dict[str, str]] = None,
    ) -> Trace:
        trace = Trace(
            operation=operation,
            source=source,
            destination=destination,
        )
        with self._lock:
            self._traces[trace.trace_id] = trace
            self._trace_count += 1
        context = TraceContext(
            trace_id=trace.trace_id,
            baggage=baggage or {},
        )
        TraceContextManager.set_current(context)
        return trace

    def add_span(
        self,
        trace_id: str,
        operation: str,
        kind: SpanKind = SpanKind.INTERNAL,
        tags: Optional[Dict[str, Any]] = None,
    ) -> Optional[Span]:
        with self._lock:
            trace = self._traces.get(trace_id)
        if not trace:
            logger.warning("Trace not found: %s", trace_id)
            return None
        context = TraceContext(trace_id=trace_id)
        span = self._span_processor.create_span(
            operation=operation,
            kind=kind,
            context=context,
            tags=tags,
        )
        if span:
            trace.add_span(span)
        return span

    def finish_span(self, trace_id: str, span_id: str, error: Optional[str] = None) -> None:
        self._span_processor.finish_span(span_id, error=error)

    def complete_trace(
        self,
        trace_id: str,
        success: bool = True,
        error: Optional[str] = None,
    ) -> Optional[Trace]:
        with self._lock:
            trace = self._traces.pop(trace_id, None)
        if trace:
            trace.finish(success=success, error=error)
            with self._lock:
                self._completed.append(trace)
                if len(self._completed) > self._max_completed:
                    self._completed = self._completed[-self._max_completed:]
            TraceContextManager.clear()
        return trace

    def get_trace(self, trace_id: str) -> Optional[Trace]:
        with self._lock:
            trace = self._traces.get(trace_id)
            if trace:
                return trace
            for t in self._completed:
                if t.trace_id == trace_id:
                    return t
            return None

    def list_active_traces(self) -> List[Trace]:
        with self._lock:
            return list(self._traces.values())

    def get_completed_traces(self, limit: int = 100) -> List[Trace]:
        with self._lock:
            return list(self._completed[-limit:])

    def search_traces(
        self,
        operation: Optional[str] = None,
        source: Optional[str] = None,
        destination: Optional[str] = None,
        min_duration_s: Optional[float] = None,
        max_duration_s: Optional[float] = None,
        success: Optional[bool] = None,
        limit: int = 50,
    ) -> List[Trace]:
        with self._lock:
            traces = list(self._completed)
        results = []
        for trace in traces:
            if operation and trace.operation != operation:
                continue
            if source and trace.source != source:
                continue
            if destination and trace.destination != destination:
                continue
            if min_duration_s and trace.duration_s < min_duration_s:
                continue
            if max_duration_s and trace.duration_s > max_duration_s:
                continue
            if success is not None and trace.success != success:
                continue
            results.append(trace)
        return results[:limit]

    def build_timeline(self, trace_id: str) -> Optional[Dict[str, Any]]:
        trace = self.get_trace(trace_id)
        if not trace:
            return None
        return trace.build_span_tree()

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._started,
                "active_count": len(self._traces),
                "completed_count": len(self._completed),
                "trace_count": self._trace_count,
                "span_processor": self._span_processor.get_stats(),
            }

    def clear(self) -> None:
        with self._lock:
            self._traces.clear()
            self._completed.clear()
            self._span_processor.flush()
