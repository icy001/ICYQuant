"""Span processor for ICYQuant Service Mesh.

Provides ``Span``, ``SpanProcessor``, and ``SpanExporter`` for
managing span lifecycle: create, process, complete, and export.
Supports sampling, aggregation, and compression.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .trace_context import TraceContext

logger = logging.getLogger(__name__)


class SpanStatus(str, Enum):
    """Span status."""

    CREATED = "created"
    ACTIVE = "active"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


class SpanKind(str, Enum):
    """Span kind."""

    REQUEST = "request"
    RPC = "rpc"
    KAFKA = "kafka"
    DATABASE = "database"
    REDIS = "redis"
    INTERNAL = "internal"


class Span:
    """A single span in a distributed trace."""

    def __init__(
        self,
        span_id: str = "",
        trace_id: str = "",
        parent_span_id: str = "",
        operation: str = "",
        kind: SpanKind = SpanKind.INTERNAL,
        context: Optional[TraceContext] = None,
    ) -> None:
        self.span_id = span_id or uuid.uuid4().hex[:16]
        self.trace_id = trace_id or (context.trace_id if context else uuid.uuid4().hex)
        self.parent_span_id = parent_span_id or (context.parent_span_id if context else "")
        self.operation = operation
        self.kind = kind
        self.status = SpanStatus.CREATED
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.duration_s: float = 0.0
        self.tags: Dict[str, Any] = {}
        self.events: List[Dict[str, Any]] = []
        self.logs: List[Dict[str, Any]] = []
        self.error: Optional[str] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self.status == SpanStatus.CREATED:
                self.status = SpanStatus.ACTIVE
                self.start_time = datetime.utcnow()

    def finish(self, error: Optional[str] = None) -> None:
        with self._lock:
            if self.status in (SpanStatus.ACTIVE, SpanStatus.CREATED):
                self.end_time = datetime.utcnow()
                if self.start_time:
                    delta = self.end_time - self.start_time
                    self.duration_s = delta.total_seconds()
                if error:
                    self.status = SpanStatus.ERROR
                    self.error = error
                else:
                    self.status = SpanStatus.COMPLETED

    def cancel(self) -> None:
        with self._lock:
            if self.status in (SpanStatus.ACTIVE, SpanStatus.CREATED):
                self.status = SpanStatus.CANCELLED
                self.end_time = datetime.utcnow()
                if self.start_time:
                    delta = self.end_time - self.start_time
                    self.duration_s = delta.total_seconds()

    def set_tag(self, key: str, value: Any) -> None:
        with self._lock:
            self.tags[key] = value

    def get_tag(self, key: str) -> Optional[Any]:
        with self._lock:
            return self.tags.get(key)

    def add_event(self, name: str, data: Optional[Dict[str, Any]] = None) -> None:
        with self._lock:
            self.events.append(
                {
                    "name": name,
                    "data": data or {},
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

    def add_log(self, level: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        with self._lock:
            self.logs.append(
                {
                    "level": level,
                    "message": message,
                    "data": data or {},
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

    @property
    def is_finished(self) -> bool:
        return self.status in (
            SpanStatus.COMPLETED,
            SpanStatus.ERROR,
            SpanStatus.CANCELLED,
        )

    @property
    def is_error(self) -> bool:
        return self.status == SpanStatus.ERROR

    @property
    def is_active(self) -> bool:
        return self.status == SpanStatus.ACTIVE

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "span_id": self.span_id,
                "trace_id": self.trace_id,
                "parent_span_id": self.parent_span_id,
                "operation": self.operation,
                "kind": self.kind.value,
                "status": self.status.value,
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
                "duration_s": self.duration_s,
                "tags": dict(self.tags),
                "events": list(self.events),
                "logs": list(self.logs),
                "error": self.error,
            }


class SamplingStrategy:
    """Span sampling strategies."""

    ALWAYS = "always"
    NEVER = "never"
    PROBABILISTIC = "probabilistic"
    RATE_LIMITED = "rate_limited"


class SpanSampler:
    """Span sampler for controlling trace volume."""

    def __init__(
        self,
        strategy: str = SamplingStrategy.PROBABILISTIC,
        sample_rate: float = 1.0,
        max_spans_per_s: float = 1000.0,
    ) -> None:
        self._strategy = strategy
        self._sample_rate = min(max(0.0, sample_rate), 1.0)
        self._max_spans_per_s = max_spans_per_s
        self._lock = threading.Lock()
        self._span_times: List[float] = []
        self._sampled_count = 0
        self._dropped_count = 0

    def should_sample(self, span: Span) -> bool:
        import random

        with self._lock:
            if self._strategy == SamplingStrategy.ALWAYS:
                self._sampled_count += 1
                return True
            elif self._strategy == SamplingStrategy.NEVER:
                self._dropped_count += 1
                return False
            elif self._strategy == SamplingStrategy.RATE_LIMITED:
                now = time.monotonic()
                self._span_times = [
                    t for t in self._span_times if now - t < 1.0
                ]
                if len(self._span_times) < self._max_spans_per_s:
                    self._span_times.append(now)
                    self._sampled_count += 1
                    return True
                self._dropped_count += 1
                return False
            else:
                if random.random() <= self._sample_rate:
                    self._sampled_count += 1
                    return True
                self._dropped_count += 1
                return False

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "strategy": self._strategy,
                "sample_rate": self._sample_rate,
                "max_spans_per_s": self._max_spans_per_s,
                "sampled_count": self._sampled_count,
                "dropped_count": self._dropped_count,
            }


class SpanExporter:
    """Exports completed spans to external systems."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._exported: List[Dict[str, Any]] = []
        self._max_exported = 10000
        self._export_count = 0
        self._error_count = 0

    def export(self, span: Span) -> bool:
        try:
            data = span.to_dict()
            with self._lock:
                self._exported.append(data)
                if len(self._exported) > self._max_exported:
                    self._exported = self._exported[-self._max_exported:]
                self._export_count += 1
            return True
        except Exception as exc:
            logger.warning("Span export failed: %s", exc)
            with self._lock:
                self._error_count += 1
            return False

    def export_batch(self, spans: List[Span]) -> Dict[str, Any]:
        success = 0
        for span in spans:
            if self.export(span):
                success += 1
        return {
            "total": len(spans),
            "exported": success,
            "failed": len(spans) - success,
        }

    def get_exported(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._exported[-limit:])

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "export_count": self._export_count,
                "error_count": self._error_count,
                "stored": len(self._exported),
            }

    def clear(self) -> None:
        with self._lock:
            self._exported.clear()


class SpanProcessor:
    """Processes spans through their lifecycle."""

    def __init__(
        self,
        sampler: Optional[SpanSampler] = None,
        exporter: Optional[SpanExporter] = None,
        batch_size: int = 100,
        flush_interval_s: float = 5.0,
    ) -> None:
        self._sampler = sampler or SpanSampler()
        self._exporter = exporter or SpanExporter()
        self._batch_size = batch_size
        self._flush_interval_s = flush_interval_s
        self._lock = threading.RLock()
        self._active_spans: Dict[str, Span] = {}
        self._completed_spans: List[Span] = []
        self._max_completed = 5000
        self._processed_count = 0
        self._last_flush = time.monotonic()

    @property
    def sampler(self) -> SpanSampler:
        return self._sampler

    @property
    def exporter(self) -> SpanExporter:
        return self._exporter

    def create_span(
        self,
        operation: str,
        kind: SpanKind = SpanKind.INTERNAL,
        context: Optional[TraceContext] = None,
        tags: Optional[Dict[str, Any]] = None,
    ) -> Optional[Span]:
        span = Span(
            operation=operation,
            kind=kind,
            context=context,
        )
        if tags:
            for k, v in tags.items():
                span.set_tag(k, v)
        if not self._sampler.should_sample(span):
            return None
        span.start()
        with self._lock:
            self._active_spans[span.span_id] = span
        return span

    def finish_span(self, span_id: str, error: Optional[str] = None) -> Optional[Span]:
        with self._lock:
            span = self._active_spans.pop(span_id, None)
        if span:
            span.finish(error=error)
            with self._lock:
                self._completed_spans.append(span)
                if len(self._completed_spans) > self._max_completed:
                    self._completed_spans = self._completed_spans[-self._max_completed:]
                self._processed_count += 1
            self._maybe_flush()
        return span

    def cancel_span(self, span_id: str) -> Optional[Span]:
        with self._lock:
            span = self._active_spans.pop(span_id, None)
        if span:
            span.cancel()
        return span

    def get_active_span(self, span_id: str) -> Optional[Span]:
        with self._lock:
            return self._active_spans.get(span_id)

    def list_active_spans(self) -> List[Span]:
        with self._lock:
            return list(self._active_spans.values())

    def get_completed_spans(self, limit: int = 100) -> List[Span]:
        with self._lock:
            return list(self._completed_spans[-limit:])

    def _maybe_flush(self) -> None:
        now = time.monotonic()
        if now - self._last_flush < self._flush_interval_s:
            return
        with self._lock:
            to_export = list(self._completed_spans)
            self._completed_spans.clear()
            self._last_flush = now
        if to_export:
            self._exporter.export_batch(to_export)

    def flush(self) -> Dict[str, Any]:
        with self._lock:
            to_export = list(self._completed_spans)
            self._completed_spans.clear()
            self._last_flush = time.monotonic()
        if to_export:
            return self._exporter.export_batch(to_export)
        return {"total": 0, "exported": 0, "failed": 0}

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "active_count": len(self._active_spans),
                "completed_count": len(self._completed_spans),
                "processed_count": self._processed_count,
                "batch_size": self._batch_size,
                "flush_interval_s": self._flush_interval_s,
                "sampler": self._sampler.get_stats(),
                "exporter": self._exporter.get_stats(),
            }
