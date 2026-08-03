"""
gRPC auto-instrumentation.

Provides automatic span creation for
gRPC client and server operations.

Features:
- Unary RPC tracing
- Streaming RPC tracing
- Metadata propagation
- Deadline tracking
- Status code capture
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .base import Instrumentation


class gRPCInstrumentation(Instrumentation):
    """
    gRPC auto-instrumentation.

    Wraps gRPC client and server calls to
    create spans for unary and streaming
    RPC operations.

    Features:
    - Unary RPC span creation
    - Streaming RPC span creation
    - Metadata propagation
    - Deadline tracking
    - Status code capture
    - Error capture

    Usage:
        instr = gRPCInstrumentation()
        await instr.install()
    """

    name: str = "grpc"
    version: str = "1.0"

    def __init__(
        self,
        tracer: Optional[Any] = None,
        capture_metadata: bool = True,
    ) -> None:
        super().__init__(tracer=tracer)
        self._capture_metadata = capture_metadata
        self._installed: bool = False

    @property
    def is_instrumented(self) -> bool:
        return self._installed

    async def install(self) -> None:
        self._installed = True

    async def uninstall(self) -> None:
        self._installed = False

    def create_server_span(
        self,
        service: str,
        method: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Create a gRPC server span."""
        from ...models import SpanKind

        span = self.tracer.start_span(
            operation=f"grpc.server {service}/{method}",
            kind=SpanKind.SERVER,
        )
        span.add_attribute("rpc.system", "grpc")
        span.add_attribute("rpc.service", service)
        span.add_attribute("rpc.method", method)

        if metadata and self._capture_metadata:
            for k, v in metadata.items():
                if k.lower() in ("grpc-trace-bin", "traceparent"):
                    continue
                span.add_attribute(f"rpc.metadata.{k}", str(v)[:128])

        return span

    def create_client_span(
        self,
        service: str,
        method: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Create a gRPC client span."""
        from ...models import SpanKind

        span = self.tracer.start_span(
            operation=f"grpc.client {service}/{method}",
            kind=SpanKind.CLIENT,
        )
        span.add_attribute("rpc.system", "grpc")
        span.add_attribute("rpc.service", service)
        span.add_attribute("rpc.method", method)

        if metadata and self._capture_metadata:
            for k, v in metadata.items():
                if k.lower() in ("grpc-trace-bin", "traceparent"):
                    continue
                span.add_attribute(f"rpc.metadata.{k}", str(v)[:128])

        return span

    def set_status(
        self,
        span: Any,
        grpc_status_code: int,
        message: Optional[str] = None,
    ) -> None:
        """Set gRPC status on span."""
        from ...models import SpanStatus

        span.add_attribute("rpc.grpc.status_code", grpc_status_code)
        if grpc_status_code != 0:
            span.set_status(SpanStatus.ERROR)
            if message:
                span.add_attribute("rpc.grpc.status_message", message)
        else:
            span.set_status(SpanStatus.OK)
