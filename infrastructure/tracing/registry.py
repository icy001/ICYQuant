"""
Trace registry.

Maintains active and finished traces,
providing lookup and lifecycle management.

Features:
- Active trace tracking
- Finished trace storage
- Trace expiration
- Span lookup by ID
- Provider and instrumentation management
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .models import SpanModel, TraceModel


class TraceRegistry:
    """
    Trace registry.

    Stores active and finished traces,
    providing lookup and lifecycle management.

    Usage:
        registry = TraceRegistry()
        registry.register(trace)
        active = registry.get_active(trace_id)
        registry.finish(trace)
        finished = registry.get_finished(trace_id)
    """

    def __init__(
        self,
        max_finished: int = 10000,
        expiration_seconds: float = 300.0,
    ) -> None:
        """
        Initialize registry.

        Args:
            max_finished: Max finished traces to store.
            expiration_seconds: Trace expiration time.
        """

        self._active: Dict[str, TraceModel] = {}
        self._finished: Dict[str, TraceModel] = {}
        self._spans: Dict[str, SpanModel] = {}
        self._max_finished = max_finished
        self._expiration = timedelta(seconds=expiration_seconds)
        self._total_created: int = 0
        self._total_finished: int = 0
        self._total_expired: int = 0

        # SDK integration
        self._provider: Optional[Any] = None
        self._tracer_provider: Optional[Any] = None
        self._instrumentations: List[Any] = []
        self._exporters: List[Any] = []
        self._processors: List[Any] = []
        self._baggage: Optional[Any] = None

    @property
    def active_count(
        self,
    ) -> int:
        """Get active trace count."""
        return len(self._active)

    @property
    def finished_count(
        self,
    ) -> int:
        """Get finished trace count."""
        return len(self._finished)

    @property
    def span_count(
        self,
    ) -> int:
        """Get total span count."""
        return len(self._spans)

    def register(
        self,
        trace: TraceModel,
    ) -> None:
        """Register a new trace."""

        self._active[trace.trace_id] = trace
        self._total_created += 1

    def register_span(
        self,
        span: SpanModel,
    ) -> None:
        """Register a span."""

        self._spans[span.span_id] = span

    def get_active(
        self,
        trace_id: str,
    ) -> Optional[TraceModel]:
        """Get an active trace."""

        return self._active.get(trace_id)

    def get_finished(
        self,
        trace_id: str,
    ) -> Optional[TraceModel]:
        """Get a finished trace."""

        return self._finished.get(trace_id)

    def get_span(
        self,
        span_id: str,
    ) -> Optional[SpanModel]:
        """Get a span by ID."""

        return self._spans.get(span_id)

    def get_trace_spans(
        self,
        trace_id: str,
    ) -> List[SpanModel]:
        """Get all spans for a trace."""

        return [
            s for s in self._spans.values()
            if s.trace_id == trace_id
        ]

    def finish(
        self,
        trace: TraceModel,
    ) -> None:
        """Move a trace from active to finished."""

        if trace.trace_id in self._active:
            del self._active[trace.trace_id]

        trace.finish()
        self._finished[trace.trace_id] = trace
        self._total_finished += 1

        # Enforce max finished limit
        if len(self._finished) > self._max_finished:
            oldest_id = next(iter(self._finished))
            del self._finished[oldest_id]

    def expire(
        self,
    ) -> int:
        """
        Expire old active traces.

        Returns:
            Number of expired traces.
        """

        now = datetime.utcnow()
        expired_ids = []

        for trace_id, trace in self._active.items():
            if now - trace.start_time > self._expiration:
                expired_ids.append(trace_id)

        for trace_id in expired_ids:
            trace = self._active[trace_id]
            trace.finish()
            self._finished[trace_id] = trace
            del self._active[trace_id]

        self._total_expired += len(expired_ids)
        return len(expired_ids)

    def clear(
        self,
    ) -> None:
        """Clear all traces and spans."""

        self._active.clear()
        self._finished.clear()
        self._spans.clear()

    # ── SDK Integration ──

    @property
    def provider(
        self,
    ) -> Optional[Any]:
        """Get the ICYTracerProvider."""
        return self._provider

    @provider.setter
    def provider(
        self,
        value: Any,
    ) -> None:
        """Set the ICYTracerProvider."""
        self._provider = value

    @property
    def tracer_provider(
        self,
    ) -> Optional[Any]:
        """Get the underlying TracerProvider."""
        return self._tracer_provider

    @tracer_provider.setter
    def tracer_provider(
        self,
        value: Any,
    ) -> None:
        """Set the underlying TracerProvider."""
        self._tracer_provider = value

    @property
    def instrumentations(
        self,
    ) -> List[Any]:
        """Get registered instrumentations."""
        return list(self._instrumentations)

    @property
    def exporters(
        self,
    ) -> List[Any]:
        """Get registered exporters."""
        return list(self._exporters)

    @property
    def processors(
        self,
    ) -> List[Any]:
        """Get registered processors."""
        return list(self._processors)

    @property
    def baggage(
        self,
    ) -> Optional[Any]:
        """Get baggage manager."""
        return self._baggage

    @baggage.setter
    def baggage(
        self,
        value: Any,
    ) -> None:
        """Set baggage manager."""
        self._baggage = value

    def add_instrumentation(
        self,
        instrumentation: Any,
    ) -> None:
        """Register an instrumentation."""
        self._instrumentations.append(instrumentation)

    def add_exporter(
        self,
        exporter: Any,
    ) -> None:
        """Register an exporter."""
        self._exporters.append(exporter)

    def add_processor(
        self,
        processor: Any,
    ) -> None:
        """Register a processor."""
        self._processors.append(processor)

    def get_stats(
        self,
    ) -> dict:
        """Get registry statistics."""

        return {
            "active": len(self._active),
            "finished": len(self._finished),
            "spans": len(self._spans),
            "total_created": self._total_created,
            "total_finished": self._total_finished,
            "total_expired": self._total_expired,
        }
