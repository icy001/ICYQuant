"""
Request and trace context.

Provides distributed tracing identifiers.
"""

from __future__ import annotations

from contextvars import ContextVar

from dataclasses import dataclass

from uuid import uuid4


_request_id: ContextVar[str | None] = (
    ContextVar(
        "request_id",
        default=None,
    )
)


_trace_id: ContextVar[str | None] = (
    ContextVar(
        "trace_id",
        default=None,
    )
)


@dataclass(
    frozen=True,
)
class TraceContext:
    __slots__ = (
        "request_id",
        "trace_id",
    )
    request_id: str
    trace_id: str


def create_context() -> TraceContext:
    return TraceContext(
        request_id=
        f"req-{uuid4().hex[:12]}",
        trace_id=
        uuid4().hex,
    )


def set_context(
    context: TraceContext,
) -> None:
    _request_id.set(
        context.request_id
    )
    _trace_id.set(
        context.trace_id
    )


def get_request_id() -> str | None:
    return _request_id.get()


def get_trace_id() -> str | None:
    return _trace_id.get()