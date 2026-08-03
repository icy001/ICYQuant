"""
Console trace exporter.

Exports spans to stdout/stderr for
development and debugging purposes.
"""

from __future__ import annotations

import json
from typing import Any, List

from .base import TraceExporter


class ConsoleExporter(TraceExporter):
    """Exports spans to console (stdout)."""

    name: str = "console"

    def __init__(self, pretty: bool = True) -> None:
        super().__init__(endpoint=None)
        self._pretty = pretty

    async def export(self, spans: List[Any]) -> bool:
        self._export_count += 1
        try:
            for span in spans:
                data = span.to_dict() if hasattr(span, "to_dict") else str(span)
                if self._pretty:
                    print(json.dumps(data, indent=2, default=str))
                else:
                    print(json.dumps(data, default=str))
            self._success_count += 1
            return True
        except Exception:
            self._failure_count += 1
            return False

    async def shutdown(self) -> None:
        pass

    async def flush(self) -> None:
        pass
