"""Jaeger trace exporter."""

from __future__ import annotations
from typing import Any, List, Optional
from .base import TraceExporter


class JaegerExporter(TraceExporter):
    """Jaeger trace exporter."""

    name: str = "jaeger"

    def __init__(self, endpoint: Optional[str] = None, **kwargs: Any) -> None:
        super().__init__(endpoint=endpoint or "localhost:14250")
        self._agent_host: str = kwargs.get("agent_host", "localhost")
        self._agent_port: int = kwargs.get("agent_port", 6831)

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
