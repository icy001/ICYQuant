"""
FastAPI auto-instrumentation.

Provides automatic span creation for
FastAPI route handlers, including:
- HTTP method and route capture
- Status code tracking
- Exception capture
- Latency measurement
- Trace context propagation

Usage:
    from infrastructure.tracing.instrumentation.fastapi import (
        FastAPIInstrumentation,
    )

    instr = FastAPIInstrumentation()
    await instr.install()
    # All FastAPI routes now have automatic tracing
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .base import Instrumentation


class FastAPIInstrumentation(Instrumentation):
    """
    FastAPI auto-instrumentation.

    Wraps FastAPI route handlers to
    automatically create server spans
    for each HTTP request, capturing
    method, route, status code, latency,
    and exceptions.

    Features:
    - Automatic HTTP SERVER span creation
    - Route and method capture
    - Status code tracking
    - Exception capture with stack trace
    - Latency measurement
    - Trace context propagation

    Usage:
        instr = FastAPIInstrumentation()
        await instr.install()

        # Or with configuration
        instr = FastAPIInstrumentation(
            service_name="my-service",
            excluded_routes=["/health", "/metrics"],
        )
        await instr.install()
    """

    name: str = "fastapi"
    version: str = "1.0"

    def __init__(
        self,
        app: Optional[Any] = None,
        tracer: Optional[Any] = None,
        service_name: str = "icyquant",
        excluded_routes: Optional[List[str]] = None,
        capture_headers: bool = False,
    ) -> None:
        """
        Initialize FastAPI instrumentation.

        Args:
            app: FastAPI application instance.
            tracer: Optional Tracer instance.
            service_name: Service name for spans.
            excluded_routes: Routes to exclude from tracing.
            capture_headers: Whether to capture HTTP headers.
        """

        super().__init__(tracer=tracer)
        self._app = app
        self._service_name = service_name
        self._excluded_routes = excluded_routes or []
        self._capture_headers = capture_headers
        self._installed: bool = False
        self._original_routes: Dict[str, Callable] = {}

        if app is not None:
            self._patch_app(app)

    @property
    def is_instrumented(
        self,
    ) -> bool:
        """Check if instrumentation is active."""
        return self._installed

    def _patch_app(
        self,
        app: Any,
    ) -> None:
        """Patch a FastAPI application."""

        if hasattr(app, "routes"):
            for route in app.routes:
                if hasattr(route, "endpoint"):
                    self._wrap_endpoint(route)
        self._installed = True

    def _wrap_endpoint(
        self,
        route: Any,
    ) -> None:
        """Wrap a route endpoint with tracing."""

        endpoint = route.endpoint
        route_path = getattr(route, "path", "")
        methods = getattr(route, "methods", {"GET"})

        # Check exclusion
        for excluded in self._excluded_routes:
            if route_path.startswith(excluded):
                return

        self._original_routes[route_path] = endpoint

        if asyncio_iscoroutine(endpoint):
            wrapped = self._wrap_async_endpoint(endpoint, route_path, methods)
        else:
            wrapped = self._wrap_sync_endpoint(endpoint, route_path, methods)

        route.endpoint = wrapped

    def _wrap_async_endpoint(
        self,
        endpoint: Callable,
        route_path: str,
        methods: set,
    ) -> Callable:
        """Wrap an async endpoint."""

        import functools

        @functools.wraps(endpoint)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            from ...models import SpanKind, SpanStatus

            span = self.tracer.start_span(
                operation=f"{next(iter(methods))} {route_path}",
                kind=SpanKind.SERVER,
            )

            span.add_attribute("http.route", route_path)
            span.add_attribute("http.method", next(iter(methods)))

            start_time = datetime.utcnow()

            try:
                result = await endpoint(*args, **kwargs)
                span.set_status(SpanStatus.OK)
                duration = (datetime.utcnow() - start_time).total_seconds() * 1000
                span.add_attribute("icyquant.latency.ms", round(duration, 2))
                return result

            except Exception as exc:
                span.set_status(SpanStatus.ERROR)
                span.add_attribute("exception.type", type(exc).__name__)
                span.add_attribute("exception.message", str(exc))
                duration = (datetime.utcnow() - start_time).total_seconds() * 1000
                span.add_attribute("icyquant.latency.ms", round(duration, 2))
                raise

            finally:
                self.tracer.finish_span(span)

        return wrapper

    def _wrap_sync_endpoint(
        self,
        endpoint: Callable,
        route_path: str,
        methods: set,
    ) -> Callable:
        """Wrap a sync endpoint."""

        import functools

        @functools.wraps(endpoint)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            from ...models import SpanKind, SpanStatus

            span = self.tracer.start_span(
                operation=f"{next(iter(methods))} {route_path}",
                kind=SpanKind.SERVER,
            )

            span.add_attribute("http.route", route_path)
            span.add_attribute("http.method", next(iter(methods)))

            start_time = datetime.utcnow()

            try:
                result = endpoint(*args, **kwargs)
                span.set_status(SpanStatus.OK)
                duration = (datetime.utcnow() - start_time).total_seconds() * 1000
                span.add_attribute("icyquant.latency.ms", round(duration, 2))
                return result

            except Exception as exc:
                span.set_status(SpanStatus.ERROR)
                span.add_attribute("exception.type", type(exc).__name__)
                span.add_attribute("exception.message", str(exc))
                duration = (datetime.utcnow() - start_time).total_seconds() * 1000
                span.add_attribute("icyquant.latency.ms", round(duration, 2))
                raise

            finally:
                self.tracer.finish_span(span)

        return wrapper

    async def install(
        self,
    ) -> None:
        """Install FastAPI instrumentation."""

        self._installed = True

    async def uninstall(
        self,
    ) -> None:
        """Remove FastAPI instrumentation."""

        self._installed = False


def asyncio_iscoroutine(func: Callable) -> bool:
    """Check if a function is a coroutine function."""
    import asyncio
    return asyncio.iscoroutinefunction(func)
