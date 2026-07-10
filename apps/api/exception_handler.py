"""
Global API exception handlers.
"""

from __future__ import annotations

from fastapi import (
    Request,
)

from fastapi.responses import (
    JSONResponse,
)

from services.observability import (
    ErrorTracker,
)


tracker = ErrorTracker()


async def global_exception_handler(
    request: Request,
    exc: Exception,
):
    error_context = tracker.capture(
        exc
    )
    return JSONResponse(
        status_code=500,
        content={
            "error":
            "internal_server_error",
            "error_id":
            error_context.error_id,
            "trace_id":
            error_context.trace_id,
        },
    )