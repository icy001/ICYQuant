"""
ICYQuant ML Platform Telemetry - Distributed tracing for ML operations.

Provides end-to-end observability across the ML lifecycle:

    Data → Feature → Dataset → Experiment → Model → Prediction

Each phase generates spans with timing, metadata, and error information.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Iterator, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class SpanKind(Enum):
    """Types of telemetry spans."""

    FEATURE_COMPUTATION = "feature_computation"
    FEATURE_PIPELINE = "feature_pipeline"
    DATASET_BUILD = "dataset_build"
    LABEL_GENERATION = "label_generation"
    TRAINING = "training"
    EVALUATION = "evaluation"
    HYPERPARAMETER_TUNING = "hyperparameter_tuning"
    CROSS_VALIDATION = "cross_validation"
    MODEL_REGISTRATION = "model_registration"
    DRIFT_DETECTION = "drift_detection"
    INFERENCE = "inference"


@dataclass
class SpanEvent:
    """An event within a span."""

    name: str
    timestamp: float = field(default_factory=time.time)
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TelemetrySpan:
    """A single telemetry span representing an operation."""

    span_id: str = field(default_factory=lambda: uuid4().hex[:12])
    trace_id: str = field(default_factory=lambda: uuid4().hex[:16])
    parent_span_id: Optional[str] = None

    name: str = ""
    kind: SpanKind = SpanKind.INFERENCE

    # Timing
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: float = 0.0

    # Status
    status: str = "ok"  # ok, error
    error: Optional[str] = None

    # Context
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[SpanEvent] = field(default_factory=list)

    # Links to other spans
    links: List[str] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return self.end_time is not None

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add an event to this span."""
        self.events.append(SpanEvent(name=name, attributes=attributes or {}))

    def set_error(self, error: str) -> None:
        """Mark this span as errored."""
        self.status = "error"
        self.error = error

    def finish(self) -> None:
        """Complete this span."""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000


class TelemetryTracer:
    """ML platform telemetry tracer.

    Tracks distributed traces across the ML lifecycle to provide
    end-to-end observability of data flow and model operations.
    """

    def __init__(self) -> None:
        self._spans: Dict[str, TelemetrySpan] = {}
        self._traces: Dict[str, List[str]] = {}  # trace_id -> [span_ids]
        self._active_spans: Dict[str, TelemetrySpan] = {}
        self._completed_spans: List[TelemetrySpan] = []

    # -- Span Management --

    def start_span(
        self,
        name: str,
        kind: SpanKind,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> TelemetrySpan:
        """Start a new telemetry span.

        Args:
            name: Operation name.
            kind: Span kind.
            trace_id: Trace ID (auto-generated if not provided).
            parent_span_id: Parent span ID for nested operations.
            attributes: Initial attributes.

        Returns:
            New TelemetrySpan.
        """
        tid = trace_id or uuid4().hex[:16]
        span = TelemetrySpan(
            trace_id=tid,
            parent_span_id=parent_span_id,
            name=name,
            kind=kind,
            attributes=attributes or {},
        )

        self._spans[span.span_id] = span
        self._active_spans[span.span_id] = span

        if tid not in self._traces:
            self._traces[tid] = []
        self._traces[tid].append(span.span_id)

        if parent_span_id and parent_span_id in self._spans:
            self._spans[parent_span_id].links.append(span.span_id)

        logger.debug("Span started: %s (kind=%s, trace=%s)", name, kind.value, tid)
        return span

    def finish_span(self, span_id: str, error: Optional[str] = None) -> Optional[TelemetrySpan]:
        """Finish a span."""
        span = self._spans.get(span_id)
        if span is None:
            return None

        if error:
            span.set_error(error)
        span.finish()
        self._active_spans.pop(span_id, None)
        self._completed_spans.append(span)
        return span

    # -- Context Manager --

    @contextmanager
    def span(
        self,
        name: str,
        kind: SpanKind,
        trace_id: Optional[str] = None,
        **attributes: Any,
    ) -> Iterator[TelemetrySpan]:
        """Context manager for automatic span lifecycle.

        Usage:
            with tracer.span("train_model", SpanKind.TRAINING, model="lightgbm") as span:
                # ... do work ...
                span.add_event("epoch_complete", {"loss": 0.1})
        """
        span = self.start_span(name, kind, trace_id=trace_id, attributes=attributes)
        try:
            yield span
        except Exception as exc:
            span.set_error(str(exc))
            raise
        finally:
            self.finish_span(span.span_id)

    # -- Trace Queries --

    def get_trace(self, trace_id: str) -> List[TelemetrySpan]:
        """Get all spans for a trace."""
        span_ids = self._traces.get(trace_id, [])
        return [self._spans[sid] for sid in span_ids if sid in self._spans]

    def get_active_spans(self) -> List[TelemetrySpan]:
        """Get all currently active spans."""
        return list(self._active_spans.values())

    def get_recent_traces(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent completed trace summaries."""
        traces: Dict[str, List[TelemetrySpan]] = {}
        for span in self._completed_spans[-limit * 10:]:
            if span.trace_id not in traces:
                traces[span.trace_id] = []
            traces[span.trace_id].append(span)

        summaries: List[Dict[str, Any]] = []
        for tid, spans in list(traces.items())[:limit]:
            total_ms = sum(s.duration_ms for s in spans)
            errors = [s.error for s in spans if s.error]
            summaries.append({
                "trace_id": tid,
                "span_count": len(spans),
                "total_duration_ms": total_ms,
                "has_errors": len(errors) > 0,
                "errors": errors[:3],
                "span_kinds": list(set(s.kind.value for s in spans)),
            })

        return summaries

    # -- Convenience Methods --

    def trace_feature_pipeline(self, feature_ids: List[str], **attrs: Any) -> TelemetrySpan:
        """Start a feature pipeline trace."""
        return self.start_span(
            "feature_pipeline",
            SpanKind.FEATURE_PIPELINE,
            attributes={"feature_count": len(feature_ids), "feature_ids": feature_ids[:10], **attrs},
        )

    def trace_training(self, model_type: str, **attrs: Any) -> TelemetrySpan:
        """Start a training trace."""
        return self.start_span(
            "model_training",
            SpanKind.TRAINING,
            attributes={"model_type": model_type, **attrs},
        )

    def trace_inference(self, model_id: str, **attrs: Any) -> TelemetrySpan:
        """Start an inference trace."""
        return self.start_span(
            "model_inference",
            SpanKind.INFERENCE,
            attributes={"model_id": model_id, **attrs},
        )
