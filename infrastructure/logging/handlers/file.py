"""
File log handler.

Writes log records to a file on disk,
with automatic directory creation and
configurable formatting.

Supports both JSON and text formats,
and handles file I/O errors gracefully
without blocking the application.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Union

from ..exceptions import HandlerError
from ..formatter import JsonFormatter, TextFormatter, get_formatter
from ..models import LogEntry
from .base import LogHandler


class FileHandler(LogHandler):
    """
    File log handler.

    Writes formatted log records to a
    file on disk. Creates parent
    directories automatically.

    Usage:
        handler = FileHandler(
            file_path="logs/app.log",
            format_type="json",
        )
        await handler.startup()
        await handler.emit(log_entry)
        await handler.shutdown()
    """

    def __init__(
        self,
        file_path: Union[str, Path],
        format_type: str = "json",
        encoding: str = "utf-8",
        name: Optional[str] = None,
    ) -> None:
        """
        Initialize file handler.

        Args:
            file_path: Path to the log file.
            format_type: Output format (json, text).
            encoding: File encoding.
            name: Optional handler name.
        """

        super().__init__(name=name)
        self._file_path = Path(file_path)
        self._formatter = get_formatter(format_type)
        self._encoding = encoding
        self._file = None

    async def startup(
        self,
    ) -> None:
        """Open the file for appending."""

        self._file_path.parent.mkdir(
            parents=True, exist_ok=True
        )
        self._file = open(
            self._file_path,
            "a",
            encoding=self._encoding,
        )
        self._started = True

    async def emit(
        self,
        record: LogEntry,
    ) -> None:
        """
        Write a log record to file.

        Args:
            record: LogEntry to write.
        """

        try:
            output = self._formatter.format(record)
            if self._file is None:
                await self.startup()
            self._file.write(output + "\n")
            self._file.flush()
            self._emit_count += 1
        except Exception:
            self._error_count += 1

    async def shutdown(
        self,
    ) -> None:
        """Close the file."""

        if self._file is not None:
            self._file.close()
            self._file = None
        self._started = False

    def get_status(
        self,
    ) -> dict:
        """Get handler status."""

        status = super().get_status()
        status["file_path"] = str(self._file_path)
        status["formatter"] = self._formatter.__class__.__name__
        return status
