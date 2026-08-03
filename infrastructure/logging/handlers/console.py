"""
Console log handler.

Outputs log records to stdout in
JSON or text format, primarily
used during development and for
containerized environments.
"""

from __future__ import annotations

import sys
from typing import Any, Optional

from ..formatter import JsonFormatter, TextFormatter, get_formatter
from ..models import LogEntry
from .base import LogHandler


class ConsoleHandler(LogHandler):
    """
    Console log handler.

    Outputs formatted log records to
    stdout. Supports both JSON and text
    formats.

    Usage:
        handler = ConsoleHandler(format_type="json")
        await handler.emit(log_entry)
    """

    def __init__(
        self,
        format_type: str = "json",
        stream: Any = None,
        name: Optional[str] = None,
    ) -> None:
        """
        Initialize console handler.

        Args:
            format_type: Output format (json, text).
            stream: Output stream (defaults to stdout).
            name: Optional handler name.
        """

        super().__init__(name=name)
        self._formatter = get_formatter(format_type)
        self._stream = stream or sys.stdout

    async def emit(
        self,
        record: LogEntry,
    ) -> None:
        """
        Emit a log record to console.

        Args:
            record: LogEntry to emit.
        """

        try:
            output = self._formatter.format(record)
            print(output, file=self._stream, flush=True)
            self._emit_count += 1
        except Exception:
            self._error_count += 1

    def get_status(
        self,
    ) -> dict:
        """Get handler status."""

        status = super().get_status()
        status["formatter"] = self._formatter.__class__.__name__
        return status
