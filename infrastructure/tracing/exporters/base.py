"""
Trace exporter base.

Defines the abstract contract that all
trace exporters must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List, Optional


class TraceExporter(ABC):
    """
    Base class for all trace exporters.

    Each exporter sends spans to a specific
    backend (Jaeger, Tempo, Zipkin, OTLP, etc.).

    Subclasses must implement export() and shutdown().
    """

    name: str = ""
    version: str = "1.0"

    def __init__(self, endpoint: Optional[str] = None) -> None:
        self._endpoint = endpoint
        self._export_count: int = 0
        self._success_count: int = 0
        self._failure_count: int = 0

    @abstractmethod
    async def export(self, spans: List[Any]) -> bool:
        """Export a batch of spans. Returns True on success."""
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown the exporter, flushing any pending data."""
        ...

    async def flush(self) -> None:
        """Flush any buffered data."""
        pass

    def get_stats(self) -> dict:
        """Get exporter statistics."""
        return {
            "name": self.name,
            "export_count": self._export_count,
            "success_count": self._success_count,
            "failure_count": self._failure_count,
            "endpoint": self._endpoint,
        }
