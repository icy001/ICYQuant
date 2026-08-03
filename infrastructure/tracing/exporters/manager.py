"""
Export manager.

Manages multiple exporters, supporting
broadcast export (send to all) and
failover strategies.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from .base import TraceExporter


class ExportManager:
    """
    Trace export manager.

    Coordinates export across multiple exporters,
    supporting broadcast mode (send to all)
    and failover mode (try next on failure).

    Features:
    - Multi-exporter support
    - Broadcast export
    - Failover export
    - Async lifecycle management
    - Statistics tracking

    Usage:
        manager = ExportManager()
        manager.register(ConsoleExporter())
        manager.register(OTLPExporter(endpoint="localhost:4317"))
        await manager.startup()
        await manager.export(spans)
        await manager.shutdown()
    """

    def __init__(
        self,
        mode: str = "broadcast",
    ) -> None:
        """
        Initialize manager.

        Args:
            mode: Export mode - "broadcast" or "failover".
        """

        self._exporters: List[TraceExporter] = []
        self._mode = mode
        self._started: bool = False

    @property
    def exporter_count(self) -> int:
        return len(self._exporters)

    @property
    def is_started(self) -> bool:
        return self._started

    def register(self, exporter: TraceExporter) -> None:
        """Register an exporter."""
        self._exporters.append(exporter)

    def unregister(self, name: str) -> None:
        """Unregister an exporter by name."""
        self._exporters = [e for e in self._exporters if e.name != name]

    def get_exporters(self) -> List[TraceExporter]:
        """Get all registered exporters."""
        return list(self._exporters)

    def get_exporter(self, name: str) -> Optional[TraceExporter]:
        """Get a specific exporter by name."""
        for e in self._exporters:
            if e.name == name:
                return e
        return None

    async def startup(self) -> None:
        """Start the export manager."""
        self._started = True

    async def export(self, spans: List[Any]) -> bool:
        """
        Export spans to all exporters.

        In broadcast mode, sends to all exporters.
        In failover mode, tries each exporter until one succeeds.

        Args:
            spans: List of spans to export.

        Returns:
            True if at least one exporter succeeded.
        """

        if not self._exporters:
            return True

        if self._mode == "broadcast":
            results = await asyncio.gather(
                *[e.export(spans) for e in self._exporters],
                return_exceptions=True,
            )
            return any(r is True for r in results)
        else:
            for exporter in self._exporters:
                try:
                    result = await exporter.export(spans)
                    if result:
                        return True
                except Exception:
                    continue
            return False

    async def flush(self) -> None:
        """Flush all exporters."""
        await asyncio.gather(
            *[e.flush() for e in self._exporters],
            return_exceptions=True,
        )

    async def shutdown(self) -> None:
        """Shutdown all exporters."""
        await asyncio.gather(
            *[e.shutdown() for e in self._exporters],
            return_exceptions=True,
        )
        self._started = False

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for all exporters."""
        return {
            "mode": self._mode,
            "started": self._started,
            "exporter_count": self.exporter_count,
            "exporters": [e.get_stats() for e in self._exporters],
        }
