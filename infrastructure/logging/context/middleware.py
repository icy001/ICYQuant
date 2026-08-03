"""
Context middleware.

Automatically creates and clears logging
context for each request, ensuring
trace_id, request_id, and correlation_id
are available throughout the request lifecycle.

Supports:
- HTTP requests (FastAPI, Starlette)
- Kafka events
- Background tasks
- Cron jobs
"""

from __future__ import annotations

import uuid
from typing import Any, Awaitable, Callable, Dict, Optional

from .manager import ContextManager
from .models import LogContext


class ContextMiddleware:
    """
    Request context middleware.

    Automatically creates a new LogContext
    with trace_id and request_id for each
    incoming request, and clears it when
    the request completes.

    For incoming requests with X-Trace-ID
    or X-Request-ID headers, the existing
    IDs are preserved for distributed tracing.

    Usage:
        middleware = ContextMiddleware()

        # Before request
        await middleware.before_request(
            headers={"X-Trace-ID": "existing-trace"},
        )

        # ... request processing ...

        # After request
        await middleware.after_request()
    """

    def __init__(
        self,
        service_name: str = "icyquant",
        environment: str = "production",
        hostname: Optional[str] = None,
    ) -> None:
        """
        Initialize middleware.

        Args:
            service_name: Service name for context.
            environment: Deployment environment.
            hostname: Machine hostname.
        """

        import socket

        self._service_name = service_name
        self._environment = environment
        self._hostname = hostname or socket.gethostname()

    async def before_request(
        self,
        headers: Optional[Dict[str, str]] = None,
        user_id: Optional[str] = None,
        **extra: Any,
    ) -> LogContext:
        """
        Create context before processing request.

        Extracts trace_id and request_id from
        headers if present (for distributed tracing),
        otherwise generates new IDs.

        Args:
            headers: Optional request headers dict.
            user_id: Optional authenticated user ID.
            **extra: Additional context fields.

        Returns:
            Created LogContext.
        """

        headers = headers or {}

        # Extract or generate trace_id
        trace_id = (
            headers.get("X-Trace-ID")
            or headers.get("x-trace-id")
            or str(uuid.uuid4())
        )

        # Extract or generate request_id
        request_id = (
            headers.get("X-Request-ID")
            or headers.get("x-request-id")
            or str(uuid.uuid4())
        )

        # Extract correlation_id if present
        correlation_id = (
            headers.get("X-Correlation-ID")
            or headers.get("x-correlation-id")
        )

        # Extract span_id if present
        span_id = (
            headers.get("X-Span-ID")
            or headers.get("x-span-id")
        )

        ctx = LogContext(
            trace_id=trace_id,
            span_id=span_id,
            request_id=request_id,
            correlation_id=correlation_id,
            user_id=user_id,
            environment=self._environment,
            hostname=self._hostname,
        )

        # Add extra fields to metadata
        if extra:
            ctx.metadata.update(extra)

        ContextManager.set(ctx)
        return ctx

    async def after_request(
        self,
    ) -> None:
        """
        Clear context after request completion.

        Ensures no context leaks between requests.
        """

        ContextManager.clear()

    async def wrap(
        self,
        handler: Callable[..., Awaitable[Any]],
        headers: Optional[Dict[str, str]] = None,
        user_id: Optional[str] = None,
        **extra: Any,
    ) -> Any:
        """
        Wrap a handler with context management.

        Creates context, runs handler, then clears
        context regardless of success/failure.

        Args:
            handler: Async callable to wrap.
            headers: Optional request headers.
            user_id: Optional user ID.
            **extra: Additional context fields.

        Returns:
            Handler result.
        """

        await self.before_request(
            headers=headers,
            user_id=user_id,
            **extra,
        )
        try:
            return await handler()
        finally:
            await self.after_request()
