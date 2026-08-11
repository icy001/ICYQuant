"""
Strategy Platform Telemetry — distributed tracing for strategy operations.

Provides end-to-end tracing across the strategy lifecycle:
    Strategy Timeline → Lifecycle Timeline → Deployment Timeline → Recovery Timeline → Audit

Each span captures timing, context, and metadata for operational visibility.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SpanKind(str, Enum):
    """Types of telemetry spans for the strategy platform."""
    # Strategy pipeline
    STRATEGY_PIPELINE = "strategy.pipeline"
    STRATEGY_DEPLOY = "strategy.deploy"
    STRATEGY_LOAD = "strategy.load"
    STRATEGY_VALIDATE = "strategy.validate"
    STRATEGY_REGISTER = "strategy.register"
    STRATEGY_PREPARE = "strategy.prepare"
    STRATEGY_START = "strategy.start"
    STRATEGY_STOP = "strategy.stop"
    STRATEGY_PAUSE = "strategy.pause"
    STRATEGY_RESUME = "strategy.resume"
    STRATEGY_EXECUTE = "strategy.execute"

    # Snapshot & Recovery
    STRATEGY_SNAPSHOT = "strategy.snapshot"
    STRATEGY_RECOVERY = "strategy.recovery"

    # Lifecycle
    STRATEGY_LIFECYCLE = "strategy.lifecycle"
    STATE_TRANSITION = "strategy.state_transition"

    # Infrastructure
    DATABASE = "strategy.db"
    CACHE = "strategy.cache"
    EXTERNAL = "strategy.external"


@dataclass
class Span:
    """A single trace span recording a unit of work."""

    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    trace_id: str = ""
    parent_span_id: str = ""
    kind: SpanKind = SpanKind.STRATEGY_PIPELINE
    name: str = ""

    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None

    # Status
    success: bool = True
    error: str = ""

    # Attributes
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Counters
    events: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        if self.ended_at is None:
            return (datetime.now(timezone.utc) - self.started_at).total_seconds() * 1000
        return (self.ended_at - self.started_at).total_seconds() * 1000

    def finish(self, success: bool = True, error: str = "") -> None:
        self.ended_at = datetime.now(timezone.utc)
        self.success = success
        if error:
            self.error = error

    def add_event(self, name: str, **attrs: Any) -> None:
        """Add a timestamped event within this span."""
        self.events.append({
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attrs": attrs,
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "kind": self.kind.value,
            "name": self.name,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_ms": round(self.duration_ms, 2),
            "success": self.success,
            "error": self.error,
            "tags": self.tags,
            "metadata": self.metadata,
            "events": self.events,
        }


@dataclass
class Trace:
    """A complete distributed trace composed of multiple spans."""

    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex[:24])
    root_span: Optional[Span] = None
    spans: List[Span] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total_duration_ms(self) -> float:
        if not self.spans:
            return 0.0
        start = min(s.started_at for s in self.spans)
        end = max(s.ended_at or datetime.now(timezone.utc) for s in self.spans)
        return (end - start).total_seconds() * 1000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "created_at": self.created_at.isoformat(),
            "total_duration_ms": round(self.total_duration_ms, 2),
            "span_count": len(self.spans),
            "root_span": self.root_span.to_dict() if self.root_span else None,
            "spans": [s.to_dict() for s in self.spans],
        }


class StrategyTelemetry:
    """Distributed tracing for the Strategy Platform.

    Creates and manages traces spanning the full strategy lifecycle,
    with hierarchical span relationships.

    Usage:
        telemetry = StrategyTelemetry()
        await telemetry.initialize()

        # Start a trace
        trace = telemetry.start_trace(strategy_id="strategy_1", name="deploy")

        # Add spans
        span = telemetry.start_span(trace, SpanKind.STRATEGY_LOAD, "load_package", parent=root_span)
        ...
        telemetry.finish_span(span, success=True)

        # Finish trace
        telemetry.finish_trace(trace, success=True)

        await telemetry.shutdown()
    """

    def __init__(self) -> None:
        self._traces: List[Trace] = []
        self._active_spans: Dict[str, Span] = {}
        self._initialized: bool = False
        self._max_traces: int = 10000
        logger.info("StrategyTelemetry created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("StrategyTelemetry initialized")

    async def shutdown(self) -> None:
        self._traces.clear()
        self._active_spans.clear()
        self._initialized = False
        logger.info("StrategyTelemetry shut down")

    # ── Trace Management ──

    def start_trace(
        self,
        strategy_id: str,
        name: str = "",
        kind: SpanKind = SpanKind.STRATEGY_PIPELINE,
        **metadata: Any,
    ) -> Trace:
        """Start a new trace for a strategy operation.

        Args:
            strategy_id: The strategy being operated on.
            name: Operation name (e.g., "deploy", "recover").
            kind: Span kind for the root span.
            **metadata: Additional trace metadata.

        Returns:
            A new Trace with a root span already created.
        """
        trace = Trace()
        root_span = Span(
            trace_id=trace.trace_id,
            kind=kind,
            name=name or f"{strategy_id}:{kind.value}",
            tags={"strategy_id": strategy_id},
            metadata=metadata,
        )
        trace.root_span = root_span
        trace.spans.append(root_span)
        self._active_spans[root_span.span_id] = root_span
        logger.debug("Trace started: %s [%s]", trace.trace_id, name)
        return trace

    def finish_trace(self, trace: Trace, success: bool = True, error: str = "") -> None:
        """Complete a trace (finishes root span and all pending spans)."""
        for span_id, span in list(self._active_spans.items()):
            if span.trace_id == trace.trace_id:
                if span.ended_at is None:
                    span.finish(success=success, error=error)
                self._active_spans.pop(span_id, None)

        if trace.root_span and trace.root_span.ended_at is None:
            trace.root_span.finish(success=success, error=error)
            self._active_spans.pop(trace.root_span.span_id, None)

        self._traces.append(trace)
        self._enforce_retention()
        logger.debug("Trace finished: %s (success=%s, spans=%d, %.1fms)",
                     trace.trace_id, success, len(trace.spans), trace.total_duration_ms)

    # ── Span Management ──

    def start_span(
        self,
        trace: Trace,
        kind: SpanKind,
        name: str,
        parent: Optional[Span] = None,
        **tags: str,
    ) -> Span:
        """Create a new span within a trace.

        Args:
            trace: The parent trace.
            kind: Span kind.
            name: Human-readable span name.
            parent: Optional parent span for hierarchy.
            **tags: Key-value tags for the span.

        Returns:
            A new Span with timing already started.
        """
        span = Span(
            trace_id=trace.trace_id,
            parent_span_id=parent.span_id if parent else (trace.root_span.span_id if trace.root_span else ""),
            kind=kind,
            name=name,
            tags=dict(tags),
        )

        # Inherit strategy_id from root
        if trace.root_span and "strategy_id" in trace.root_span.tags:
            span.tags.setdefault("strategy_id", trace.root_span.tags["strategy_id"])

        trace.spans.append(span)
        self._active_spans[span.span_id] = span
        return span

    def finish_span(self, span: Span, success: bool = True, error: str = "") -> None:
        """Complete a span."""
        span.finish(success=success, error=error)
        self._active_spans.pop(span.span_id, None)

    # ── Query ──

    def get_trace(self, trace_id: str) -> Optional[Trace]:
        """Retrieve a trace by ID."""
        for t in self._traces:
            if t.trace_id == trace_id:
                return t
        return None

    def list_traces(
        self,
        strategy_id: Optional[str] = None,
        limit: int = 50,
        success_only: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """List recent traces with optional filtering."""
        traces = self._traces
        if strategy_id:
            traces = [
                t for t in traces
                if t.root_span and t.root_span.tags.get("strategy_id") == strategy_id
            ]
        if success_only is not None:
            traces = [
                t for t in traces
                if t.root_span and t.root_span.success == success_only
            ]
        # Most recent first
        traces = sorted(traces, key=lambda t: t.created_at, reverse=True)
        return [t.to_dict() for t in traces[:limit]]

    def list_failures(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List failed traces."""
        return self.list_traces(success_only=False, limit=limit)

    def get_span_tree(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Get the hierarchical span tree for a trace."""
        trace = self.get_trace(trace_id)
        if trace is None:
            return None

        span_map = {s.span_id: s for s in trace.spans}
        tree = []

        def build_subtree(parent_id: str) -> List[Dict[str, Any]]:
            children = []
            for s in trace.spans:
                if s.parent_span_id == parent_id:
                    node = s.to_dict()
                    node["children"] = build_subtree(s.span_id)
                    children.append(node)
            return children

        if trace.root_span:
            tree = build_subtree(trace.root_span.span_id)
            return {
                "trace_id": trace_id,
                "root": trace.root_span.to_dict(),
                "flat_spans": len(trace.spans),
                "tree": tree,
            }
        return None

    # ── Internals ──

    def _enforce_retention(self) -> None:
        """Enforce maximum trace retention."""
        if len(self._traces) > self._max_traces:
            overflow = len(self._traces) - self._max_traces
            self._traces = self._traces[overflow:]

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_traces": len(self._traces),
            "active_spans": len(self._active_spans),
            "initialized": self._initialized,
        }
