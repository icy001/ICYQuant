"""Zipkin trace exporter."""

from __future__ import annotations
from typing import Any, List, Optional
from .base import TraceExporter


class ZipkinExporter(TraceExporter):
    """Zipkin trace exporter."""

    name: str = "zipkin"

    def __init__(self, endpoint: Optional[str] = None, **kwargs: Any) -> None:
        super().__init__(endpoint=endpoint or "http://localhost:9411/api/v2/spans")
        self._timeout: float = kwargs.get("timeout", 30.0)

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
