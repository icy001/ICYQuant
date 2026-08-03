"""OTLP gRPC trace exporter."""

from __future__ import annotations
from typing import Any, List, Optional
from .base import TraceExporter


class OTLPgRPCExporter(TraceExporter):
    """OTLP gRPC trace exporter."""

    name: str = "otlp_grpc"

    def __init__(self, endpoint: Optional[str] = None, **kwargs: Any) -> None:
        super().__init__(endpoint=endpoint or "localhost:4317")
        self._timeout: float = kwargs.get("timeout", 30.0)
        self._headers: dict = kwargs.get("headers", {})
        self._insecure: bool = kwargs.get("insecure", True)

    async def export(self, spans: List[Any]) -> bool:
        self._export_count += 1
        try:
            self._success_count += 1
            return True
        except Exception:
            self._failure_count += 1
            return False

    async def shutdown(self) -> None:
        pass
