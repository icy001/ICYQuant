"""
Telemetry — End-to-end tracing for evolution operations.

Traces:
    - Evolution run lifecycle
    - Generation transitions
    - Mutation/crossover events
    - Fitness evaluation
    - Validation pipeline
    - Promotion events
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TelemetrySpan:
    """A single telemetry span."""

    def __init__(self, name: str, parent_id: Optional[str] = None):
        self.span_id = uuid.uuid4().hex[:16]
        self.parent_id = parent_id
        self.name = name
        self.started_at = datetime.now(timezone.utc)
        self.finished_at: Optional[datetime] = None
        self.attributes: Dict[str, Any] = {}
        self.events: List[Dict[str, Any]] = []

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        self.events.append({
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attributes": attributes or {},
        })

    def finish(self) -> None:
        self.finished_at = datetime.now(timezone.utc)

    @property
    def duration_ms(self) -> float:
        if self.finished_at:
            return (self.finished_at - self.started_at).total_seconds() * 1000
        return 0


class EvolutionTelemetry:
    """Telemetry for evolution operations."""

    def __init__(self):
        self._spans: Dict[str, TelemetrySpan] = {}
        self._active_span: Optional[TelemetrySpan] = None

    def start_span(self, name: str, **attributes) -> TelemetrySpan:
        parent_id = self._active_span.span_id if self._active_span else None
        span = TelemetrySpan(name, parent_id)
        for k, v in attributes.items():
            span.set_attribute(k, v)
        self._spans[span.span_id] = span
        self._active_span = span
        return span

    def finish_span(self, span: Optional[TelemetrySpan] = None) -> None:
        target = span or self._active_span
        if target:
            target.finish()
            if self._active_span and self._active_span.span_id == target.span_id:
                self._active_span = (
                    self._spans.get(target.parent_id) if target.parent_id else None
                )
            logger.debug("Span %s finished: %.0fms", target.name, target.duration_ms)

    def get_trace(self, span_id: str) -> Optional[Dict[str, Any]]:
        span = self._spans.get(span_id)
        if not span:
            return None
        return {
            "span_id": span.span_id,
            "parent_id": span.parent_id,
            "name": span.name,
            "duration_ms": span.duration_ms,
            "attributes": span.attributes,
            "events": span.events,
        }
