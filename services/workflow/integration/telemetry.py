"""Integration Telemetry — tracing, logging, and metrics for platform integrations.

Unified pipeline::

    Platform Integration → Tracing → Logging → Metrics → Audit
"""

from __future__ import annotations

import contextlib
import logging
import time
import uuid
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

from .metrics import IntegrationMetrics

logger = logging.getLogger(__name__)

platform_trace_id: ContextVar[Optional[str]] = ContextVar("platform_trace_id", default=None)


class IntegrationSpan:
    """A tracing span for a platform operation."""

    def __init__(self, name: str, *, trace_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        self.span_id = str(uuid.uuid4())[:8]
        self.name = name
        self.trace_id = trace_id or platform_trace_id.get() or str(uuid.uuid4())[:16]
        self.metadata = metadata or {}
        self.start_time = time.monotonic()
        self.end_time: Optional[float] = None
        self.events: List[Dict[str, Any]] = []

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        self.events.append({"name": name, "timestamp": datetime.utcnow().isoformat(), "attributes": attributes or {}})

    def finish(self) -> None:
        self.end_time = time.monotonic()

    @property
    def duration_seconds(self) -> float:
        if self.end_time is None:
            return time.monotonic() - self.start_time
        return self.end_time - self.start_time


class IntegrationTelemetry:
    """Unified telemetry for platform integration operations."""

    def __init__(self, *, metrics: Optional[IntegrationMetrics] = None) -> None:
        self._metrics = metrics or IntegrationMetrics()
        self._spans: List[IntegrationSpan] = []
        self._max_spans = 10000

    @contextlib.contextmanager
    def trace(self, name: str, *, metadata: Optional[Dict[str, Any]] = None) -> Generator[IntegrationSpan, None, None]:
        span = IntegrationSpan(name=name, metadata=metadata)
        token = platform_trace_id.set(span.trace_id)
        try:
            yield span
        finally:
            platform_trace_id.reset(token)
            span.finish()
            self._spans.append(span)
            if len(self._spans) > self._max_spans:
                self._spans = self._spans[-self._max_spans:]

    def get_spans(self, limit: int = 100) -> List[Dict[str, Any]]:
        return [{"span_id": s.span_id, "name": s.name, "duration_seconds": round(s.duration_seconds, 6)} for s in self._spans[-limit:]]

    def snapshot(self) -> Dict[str, Any]:
        return {"span_count": len(self._spans), "metrics": self._metrics.get_all_metrics()}
