"""Trace context propagation for ICYQuant Service Mesh.

Provides ``TraceContext`` and ``TraceContextManager`` for propagating
trace identifiers across service boundaries, supporting both
synchronous and asynchronous trace propagation.
"""

from __future__ import annotations

import logging
import threading
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TraceContext:
    """Trace context with identifiers and baggage."""

    def __init__(
        self,
        trace_id: str = "",
        span_id: str = "",
        parent_span_id: str = "",
        baggage: Optional[Dict[str, str]] = None,
    ) -> None:
        self.trace_id = trace_id or self._generate_trace_id()
        self.span_id = span_id or self._generate_span_id()
        self.parent_span_id = parent_span_id
        self.baggage: Dict[str, str] = baggage or {}

    @staticmethod
    def _generate_trace_id() -> str:
        return uuid.uuid4().hex

    @staticmethod
    def _generate_span_id() -> str:
        return uuid.uuid4().hex[:16]

    def add_baggage(self, key: str, value: str) -> None:
        self.baggage[key] = value

    def get_baggage(self, key: str) -> Optional[str]:
        return self.baggage.get(key)

    def remove_baggage(self, key: str) -> bool:
        if key in self.baggage:
            del self.baggage[key]
            return True
        return False

    def child_span_context(self) -> TraceContext:
        """Create a child trace context."""
        return TraceContext(
            trace_id=self.trace_id,
            parent_span_id=self.span_id,
            baggage=dict(self.baggage),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "baggage": dict(self.baggage),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TraceContext:
        return cls(
            trace_id=data.get("trace_id", ""),
            span_id=data.get("span_id", ""),
            parent_span_id=data.get("parent_span_id", ""),
            baggage=data.get("baggage", {}),
        )

    def to_headers(self) -> Dict[str, str]:
        """Serialize context to HTTP headers."""
        headers = {
            "X-Trace-Id": self.trace_id,
            "X-Span-Id": self.span_id,
        }
        if self.parent_span_id:
            headers["X-Parent-Span-Id"] = self.parent_span_id
        for key, value in self.baggage.items():
            headers[f"X-Baggage-{key}"] = value
        return headers

    @classmethod
    def from_headers(cls, headers: Dict[str, str]) -> TraceContext:
        """Extract context from HTTP headers."""
        trace_id = headers.get("X-Trace-Id", "")
        span_id = headers.get("X-Span-Id", "")
        parent_span_id = headers.get("X-Parent-Span-Id", "")
        baggage: Dict[str, str] = {}
        for key, value in headers.items():
            if key.startswith("X-Baggage-"):
                baggage_key = key[len("X-Baggage-"):]
                baggage[baggage_key] = value
        return cls(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            baggage=baggage,
        )

    def __repr__(self) -> str:
        return (
            f"TraceContext(trace_id={self.trace_id[:8]}..., "
            f"span_id={self.span_id[:8]}...)"
        )


class TraceContextManager:
    """Manages trace contexts for async propagation."""

    _local = threading.local()

    @classmethod
    def get_current(cls) -> Optional[TraceContext]:
        return getattr(cls._local, "context", None)

    @classmethod
    def set_current(cls, context: Optional[TraceContext]) -> None:
        cls._local.context = context

    @classmethod
    def clear(cls) -> None:
        cls._local.context = None

    @classmethod
    def start_trace(cls, baggage: Optional[Dict[str, str]] = None) -> TraceContext:
        context = TraceContext(baggage=baggage)
        cls.set_current(context)
        return context

    @classmethod
    def continue_trace(cls, headers: Dict[str, str]) -> TraceContext:
        context = TraceContext.from_headers(headers)
        child = context.child_span_context()
        cls.set_current(child)
        return child

    @classmethod
    def get_trace_id(cls) -> str:
        ctx = cls.get_current()
        return ctx.trace_id if ctx else ""

    @classmethod
    def get_span_id(cls) -> str:
        ctx = cls.get_current()
        return ctx.span_id if ctx else ""
