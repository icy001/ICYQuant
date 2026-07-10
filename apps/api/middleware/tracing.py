"""
Request tracing middleware.

Creates request and trace identifiers
for every API request.
"""

from __future__ import annotations

from fastapi import Request

from starlette.middleware.base import (
    BaseHTTPMiddleware,
)

from services.observability import (
    create_context,
    set_context,
)


class TraceMiddleware(
    BaseHTTPMiddleware
):
    async def dispatch(
        self,
        request: Request,
        call_next,
    ):
        context = create_context()
        set_context(
            context
        )
        request.state.request_id = (
            context.request_id
        )
        request.state.trace_id = (
            context.trace_id
        )
        response = await call_next(
            request
        )
        response.headers[
            "X-Request-ID"
        ] = context.request_id
        response.headers[
            "X-Trace-ID"
        ] = context.trace_id
        return response