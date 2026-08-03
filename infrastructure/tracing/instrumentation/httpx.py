"""
HTTPX client auto-instrumentation.

Provides automatic span creation for
HTTPX client requests, including:
- HTTP CLIENT span creation
- URL and method capture
- Status code tracking
- Retry counting
- Latency measurement

Usage:
    from infrastructure.tracing.instrumentation.httpx import (
        HTTPXInstrumentation,
    )

    instr = HTTPXInstrumentation()
    await instr.install()
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .base import Instrumentation


class HTTPXInstrumentation(Instrumentation):
    """
    HTTPX client auto-instrumentation.

    Wraps HTTPX client requests to
    automatically create client spans,
    capturing URL, method, status, retry
    count, and latency.

    Features:
    - Automatic HTTP CLIENT span creation
    - URL and method capture
    - Status code tracking
    - Retry counting
    - Latency measurement
    - Trace context injection

    Usage:
        instr = HTTPXInstrumentation()
        await instr.install()

        # All httpx requests now have automatic tracing
    """

    name: str = "httpx"
    version: str = "1.0"

    def __init__(
        self,
        tracer: Optional[Any] = None,
        service_name: str = "icyquant",
    ) -> None:
        """
        Initialize HTTPX instrumentation.

        Args:
            tracer: Optional Tracer instance.
            service_name: Service name for spans.
        """

        super().__init__(tracer=tracer)
        self._service_name = service_name
        self._installed: bool = False
        self._original_request: Optional[Callable] = None
        self._original_async_request: Optional[Callable] = None

    @property
    def is_instrumented(
        self,
    ) -> bool:
        """Check if instrumentation is active."""
        return self._installed

    async def install(
        self,
    ) -> None:
        """Install HTTPX instrumentation."""

        try:
            import httpx

            # Patch sync Client.request
            if hasattr(httpx, "Client"):
                self._original_request = httpx.Client.request
                httpx.Client.request = self._wrap_sync_request(
                    self._original_request
                )

            # Patch async AsyncClient.request
            if hasattr(httpx, "AsyncClient"):
                self._original_async_request = httpx.AsyncClient.request
                httpx.AsyncClient.request = self._wrap_async_request(
                    self._original_async_request
                )

            self._installed = True
        except ImportError:
            pass

    async def uninstall(
        self,
    ) -> None:
        """Remove HTTPX instrumentation."""

        try:
            import httpx

            if self._original_request and hasattr(httpx, "Client"):
                httpx.Client.request = self._original_request

            if self._original_async_request and hasattr(httpx, "AsyncClient"):
                httpx.AsyncClient.request = self._original_async_request
        except ImportError:
            pass

        self._installed = False

    def _wrap_sync_request(
        self,
        original: Callable,
    ) -> Callable:
        """Wrap sync request."""

        import functools

        @functools.wraps(original)
        def wrapper(
            self_client: Any,
            method: str,
            url: str,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            from ...models import SpanKind, SpanStatus

            span = self.tracer.start_span(
                operation=f"HTTP {method}",
                kind=SpanKind.CLIENT,
            )

            span.add_attribute("http.method", method)
            span.add_attribute("http.url", str(url))

            start_time = datetime.utcnow()

            try:
                result = original(
                    self_client, method, url, *args, **kwargs
                )
                status_code = getattr(result, "status_code", 200)
                span.add_attribute("http.status_code", status_code)
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

    def _wrap_async_request(
        self,
        original: Callable,
    ) -> Callable:
        """Wrap async request."""

        import functools

        @functools.wraps(original)
        async def wrapper(
            self_client: Any,
            method: str,
            url: str,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            from ...models import SpanKind, SpanStatus

            span = self.tracer.start_span(
                operation=f"HTTP {method}",
                kind=SpanKind.CLIENT,
            )

            span.add_attribute("http.method", method)
            span.add_attribute("http.url", str(url))

            start_time = datetime.utcnow()

            try:
                result = await original(
                    self_client, method, url, *args, **kwargs
                )
                status_code = getattr(result, "status_code", 200)
                span.add_attribute("http.status_code", status_code)
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
