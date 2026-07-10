"""
FastAPI OpenTelemetry middleware.
"""

from __future__ import annotations

from fastapi import Request

from starlette.middleware.base import (
    BaseHTTPMiddleware,
)

from services.observability.tracing import (
    Tracer,
)


tracer = Tracer(
    "icyquant-api"
)


class OpenTelemetryMiddleware(
    BaseHTTPMiddleware
):
    async def dispatch(
        self,
        request: Request,
        call_next,
    ):
        span = tracer.create_span(
            operation=(
                request.method
                +
                " "
                +
                request.url.path
            )
        )
        request.state.trace_id = (
            span.trace_id
        )
        request.state.span_id = (
            span.span_id
        )
        response = await call_next(
            request
        )
        response.headers[
            "X-Trace-ID"
        ] = span.trace_id
        response.headers[
            "X-Span-ID"
        ] = span.span_id
        return response