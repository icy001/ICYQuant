"""
Tracing middleware.

Provides middleware for HTTP frameworks
that automatically creates spans for
incoming requests, injecting trace
context propagation and business
attribute enrichment.

Features:
- Automatic span creation for HTTP requests
- Trace context injection/extraction
- Baggage propagation
- Business attribute enrichment
- Error capture
- Performance timing
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .context import (
    clear_trace,
    current_span,
    current_trace,
    set_span,
    set_trace,
)
from .hooks import fire_hook, get_hooks
from .models import SpanKind, SpanModel, SpanStatus, TraceModel
from .propagator import ICYTracePropagator
from .tracer import Tracer


class TraceMiddleware:
    """
    HTTP tracing middleware.

    Automatically creates spans for incoming
    HTTP requests, extracts trace context from
    headers, and enriches spans with business
    attributes.

    Usage:
        # FastAPI
        from fastapi import FastAPI
        app = FastAPI()
        app.add_middleware(TraceMiddleware)

        # Starlette
        from starlette.applications import Starlette
        app = Starlette()
        app.add_middleware(TraceMiddleware)
    """

    def __init__(
        self,
        app: Optional[Any] = None,
        tracer: Optional[Tracer] = None,
        service_name: str = "icyquant",
        enabled: bool = True,
        capture_headers: bool = False,
        excluded_routes: Optional[List[str]] = None,
        business_attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize middleware.

        Args:
            app: Optional ASGI application.
            tracer: Optional Tracer instance.
            service_name: Service name for spans.
            enabled: Whether tracing is enabled.
            capture_headers: Whether to capture HTTP headers.
            excluded_routes: Routes to exclude from tracing.
            business_attributes: Default business attributes.
        """

        self._app = app
        self._tracer = tracer or Tracer()
        self._service_name = service_name
        self._enabled = enabled
        self._capture_headers = capture_headers
        self._excluded_routes = excluded_routes or []
        self._business_attributes = business_attributes or {}
        self._propagator = ICYTracePropagator()

        if app is not None:
            self._patch_app(app)

    def _patch_app(self, app: Any) -> None:
        """Patch the ASGI application with trace middleware."""

        if hasattr(app, "user_middleware") or hasattr(app, "middleware"):
            # Starlette/FastAPI style
            app.user_middleware = [
                m for m in getattr(app, "user_middleware", [])
                if m.cls != TraceMiddleware
            ]
            # Insert at beginning
            app.user_middleware.insert(
                0,
                type(
                    "TraceMiddlewareWrapper",
                    (),
                    {"cls": TraceMiddleware, "options": {}},
                ),
            )

    async def __call__(
        self,
        scope: Dict[str, Any],
        receive: Callable,
        send: Callable,
    ) -> None:
        """
        Handle an ASGI request.

        Args:
            scope: ASGI scope dict.
            receive: Receive coroutine.
            send: Send coroutine.
        """

        if not self._enabled:
            await self._app(scope, receive, send)
            return

        # Only handle HTTP requests
        if scope["type"] not in ("http", "websocket"):
            await self._app(scope, receive, send)
            return

        # Check excluded routes
        path = scope.get("path", "")
        for excluded in self._excluded_routes:
            if path.startswith(excluded):
                await self._app(scope, receive, send)
                return

        # Extract trace context from headers
        headers = self._get_headers(scope)
        extracted_context = self._propagator.extract(headers)

        # Start span
        span = self._tracer.start_span(
            operation=f"{scope.get('method', 'GET')} {path}",
            kind=SpanKind.SERVER,
        )

        # Set HTTP attributes
        self._set_http_attributes(span, scope, headers)

        # Set business attributes
        for key, value in self._business_attributes.items():
            span.add_attribute(key, value)

        # Extract baggage
        baggage_items = self._propagator.extract_baggage(headers)
        for key, value in baggage_items.items():
            span.add_attribute(f"baggage.{key}", value)

        # Fire hooks
        hooks = get_hooks()
        hooks.fire("on_span_start", span)
        hooks.fire("before_request", span, scope)

        start_time = datetime.utcnow()
        status_code = 200
        error = None

        # Intercept send to capture status
        async def send_wrapper(message: Dict[str, Any]) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 200)
            await send(message)

        try:
            await self._app(scope, receive, send_wrapper)
            span.set_status(SpanStatus.OK)
        except Exception as exc:
            span.set_status(SpanStatus.ERROR)
            span.add_attribute("exception.type", type(exc).__name__)
            span.add_attribute("exception.message", str(exc))
            error = exc
            hooks.fire("on_error", span, exc)
            raise
        finally:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            span.add_attribute("http.status_code", status_code)
            span.add_attribute("icyquant.latency.ms", round(duration_ms, 2))
            span.add_attribute(
                "outcome",
                "success" if 200 <= status_code < 400 else "failure",
            )

            # Fire hooks
            hooks.fire("after_request", span, {"status_code": status_code})
            hooks.fire("on_span_end", span)

            self._tracer.finish_span(
                span,
                status=SpanStatus.ERROR if error else SpanStatus.OK,
            )

            # Clear context
            clear_trace()

    def _get_headers(
        self,
        scope: Dict[str, Any],
    ) -> Dict[str, str]:
        """Extract headers from ASGI scope."""

        headers = {}
        for key, value in scope.get("headers", []):
            key_str = key.decode("utf-8") if isinstance(key, bytes) else key
            value_str = value.decode("utf-8") if isinstance(value, bytes) else value
            headers[key_str] = value_str
        return headers

    def _set_http_attributes(
        self,
        span: SpanModel,
        scope: Dict[str, Any],
        headers: Dict[str, str],
    ) -> None:
        """Set HTTP attributes on span."""

        method = scope.get("method", "GET")
        path = scope.get("path", "")
        query_string = scope.get("query_string", b"")
        scheme = scope.get("scheme", "http")
        server = scope.get("server")
        client = scope.get("client")
        root_path = scope.get("root_path", "")

        full_path = f"{root_path}{path}"
        if query_string:
            qs = query_string.decode("utf-8") if isinstance(query_string, bytes) else query_string
            full_path = f"{full_path}?{qs}"

        span.add_attribute("http.method", method)
        span.add_attribute("http.target", full_path)
        span.add_attribute("url.path", path)
        span.add_attribute("url.scheme", scheme)

        if server:
            span.add_attribute("net.host.name", server[0])
            span.add_attribute("net.host.port", server[1])

        if client:
            span.add_attribute("net.peer.name", client[0])
            span.add_attribute("net.peer.port", client[1])
            span.add_attribute("http.client_ip", client[0])

        # Capture headers if configured
        if self._capture_headers:
            for key, value in headers.items():
                if key.lower() in (
                    "user-agent", "content-type", "x-request-id",
                    "x-correlation-id", "x-tenant-id",
                ):
                    span.add_attribute(f"http.header.{key.lower()}", value)

    def get_tracer(self) -> Tracer:
        """Get the tracer instance."""
        return self._tracer


class TraceContextInjector:
    """
    Client-side trace context injector.

    Injects trace context headers into
    outgoing requests, ensuring propagation
    across service boundaries.

    Usage:
        injector = TraceContextInjector()
        headers = {}
        injector.inject(headers)
        # headers now contains traceparent, X-Trace-ID, etc.
    """

    def __init__(
        self,
        propagator: Optional[ICYTracePropagator] = None,
    ) -> None:
        """Initialize injector."""
        self._propagator = propagator or ICYTracePropagator()

    def inject(
        self,
        carrier: Dict[str, str],
        baggage: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """
        Inject current trace context into carrier.

        Args:
            carrier: Headers dict to inject into.
            baggage: Optional baggage items.

        Returns:
            Updated carrier dict.
        """

        span = current_span()
        if span is not None:
            return self._propagator.inject(carrier, span=span, baggage=baggage)
        return carrier

    def extract(
        self,
        carrier: Dict[str, str],
    ) -> Optional[Dict[str, str]]:
        """
        Extract trace context from carrier.

        Args:
            carrier: Headers dict to extract from.

        Returns:
            Extracted context or None.
        """

        return self._propagator.extract(carrier)


# Starlette/FastAPI compatibility
try:
    from starlette.types import ASGIApp, Receive, Scope, Send

    async def _starlette_middleware(
        app: ASGIApp,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        """Starlette-compatible middleware function."""
        middleware = scope.get("state", {}).get("trace_middleware")
        if middleware:
            await middleware(scope, receive, send)
        else:
            await app(scope, receive, send)
except ImportError:
    pass
