"""
Correlation context for trading lifecycle tracing.
"""

from __future__ import annotations

from contextvars import ContextVar

from dataclasses import dataclass

from uuid import uuid4


_correlation_context: ContextVar[
    "CorrelationContext | None"
] = ContextVar(
    "correlation_context",
    default=None,
)


@dataclass(
    frozen=True,
)
class CorrelationContext:
    correlation_id: str
    request_id: str | None = None
    trace_id: str | None = None
    user_id: str | None = None
    order_id: str | None = None
    event_id: str | None = None


def create_correlation(
    request_id: str | None = None,
    trace_id: str | None = None,
    user_id: str | None = None,
) -> CorrelationContext:
    return CorrelationContext(
        correlation_id=(
            f"corr-{uuid4().hex[:12]}"
        ),
        request_id=request_id,
        trace_id=trace_id,
        user_id=user_id,
    )


def set_correlation(
    context: CorrelationContext,
):
    _correlation_context.set(
        context
    )


def get_correlation(
) -> CorrelationContext | None:
    return (
        _correlation_context.get()
    )


def update_order(
    order_id: str,
):
    current = get_correlation()

    if current is None:
        return

    set_correlation(
        CorrelationContext(
            correlation_id=
            current.correlation_id,
            request_id=
            current.request_id,
            trace_id=
            current.trace_id,
            user_id=
            current.user_id,
            order_id=
            order_id,
            event_id=
            current.event_id,
        )
    )


def update_event(
    event_id: str,
):
    current = get_correlation()

    if current is None:
        return

    set_correlation(
        CorrelationContext(
            correlation_id=
            current.correlation_id,
            request_id=
            current.request_id,
            trace_id=
            current.trace_id,
            user_id=
            current.user_id,
            order_id=
            current.order_id,
            event_id=
            event_id,
        )
    )