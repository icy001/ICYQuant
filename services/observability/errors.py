"""
Error tracking service.

Provides production exception tracking.
"""

from __future__ import annotations

from dataclasses import dataclass

from uuid import uuid4

from datetime import datetime, timezone

from .context import (
    get_request_id,
    get_trace_id,
)


@dataclass(
    frozen=True,
)
class ErrorContext:
    __slots__ = (
        "error_id",
        "request_id",
        "trace_id",
        "timestamp",
    )
    error_id: str
    request_id: str | None
    trace_id: str | None
    timestamp: str


def create_error_context() -> ErrorContext:
    return ErrorContext(
        error_id=
        f"err-{uuid4().hex[:12]}",
        request_id=
        get_request_id(),
        trace_id=
        get_trace_id(),
        timestamp=
        datetime.now(
            timezone.utc
        ).isoformat(),
    )


class ErrorTracker:
    def capture(
        self,
        exception: Exception,
    ) -> ErrorContext:
        context = create_error_context()
        return context