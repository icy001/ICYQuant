"""
Context propagator.

Handles propagation of logging context
across service boundaries via headers,
enabling distributed tracing across
HTTP, Kafka, gRPC, and other transports.

Supports inject (outgoing) and extract
(incoming) operations for bidirectional
context propagation.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .manager import ContextManager
from .models import LogContext

# Standard header names for context propagation
HEADER_TRACE_ID = "X-Trace-ID"
HEADER_SPAN_ID = "X-Span-ID"
HEADER_REQUEST_ID = "X-Request-ID"
HEADER_CORRELATION_ID = "X-Correlation-ID"
HEADER_USER_ID = "X-User-ID"
HEADER_STRATEGY_ID = "X-Strategy-ID"
HEADER_ORDER_ID = "X-Order-ID"
HEADER_SESSION_ID = "X-Session-ID"

# All propagation headers
PROPAGATION_HEADERS = (
    HEADER_TRACE_ID,
    HEADER_SPAN_ID,
    HEADER_REQUEST_ID,
    HEADER_CORRELATION_ID,
    HEADER_USER_ID,
    HEADER_STRATEGY_ID,
    HEADER_ORDER_ID,
    HEADER_SESSION_ID,
)


class ContextPropagator:
    """
    Distributed context propagator.

    Injects the current logging context
    into outgoing headers and extracts
    context from incoming headers.

    Usage:
        propagator = ContextPropagator()

        # Outgoing request
        headers = {}
        propagator.inject(headers)
        # headers now contain X-Trace-ID, etc.

        # Incoming request
        ctx = propagator.extract(headers)
        ContextManager.set(ctx)
    """

    def inject(
        self,
        headers: Dict[str, str],
        context: Optional[LogContext] = None,
    ) -> Dict[str, str]:
        """
        Inject context into headers.

        Args:
            headers: Headers dict to inject into.
            context: Optional context (defaults to current).

        Returns:
            Updated headers dict.
        """

        ctx = context or ContextManager.get()

        if ctx.trace_id:
            headers[HEADER_TRACE_ID] = ctx.trace_id
        if ctx.span_id:
            headers[HEADER_SPAN_ID] = ctx.span_id
        if ctx.request_id:
            headers[HEADER_REQUEST_ID] = ctx.request_id
        if ctx.correlation_id:
            headers[HEADER_CORRELATION_ID] = ctx.correlation_id
        if ctx.user_id:
            headers[HEADER_USER_ID] = ctx.user_id
        if ctx.strategy_id:
            headers[HEADER_STRATEGY_ID] = ctx.strategy_id
        if ctx.order_id:
            headers[HEADER_ORDER_ID] = ctx.order_id
        if ctx.session_id:
            headers[HEADER_SESSION_ID] = ctx.session_id

        return headers

    def extract(
        self,
        headers: Dict[str, str],
    ) -> LogContext:
        """
        Extract context from headers.

        Handles case-insensitive header names.

        Args:
            headers: Headers dict to extract from.

        Returns:
            Extracted LogContext.
        """

        # Build case-insensitive lookup
        lower_headers = {
            k.lower(): v for k, v in headers.items()
        }

        def _get(
            name: str,
        ) -> Optional[str]:
            return lower_headers.get(name.lower())

        return LogContext(
            trace_id=_get(HEADER_TRACE_ID),
            span_id=_get(HEADER_SPAN_ID),
            request_id=_get(HEADER_REQUEST_ID),
            correlation_id=_get(HEADER_CORRELATION_ID),
            user_id=_get(HEADER_USER_ID),
            strategy_id=_get(HEADER_STRATEGY_ID),
            order_id=_get(HEADER_ORDER_ID),
            session_id=_get(HEADER_SESSION_ID),
        )

    def extract_and_set(
        self,
        headers: Dict[str, str],
    ) -> LogContext:
        """
        Extract context from headers and set as current.

        Args:
            headers: Headers dict to extract from.

        Returns:
            Extracted and set LogContext.
        """

        ctx = self.extract(headers)

        # Merge with existing context (preserve environment/hostname)
        current = ContextManager.get()
        merged = current.merge(ctx)
        ContextManager.set(merged)

        return merged
