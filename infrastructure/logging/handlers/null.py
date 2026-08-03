"""
Null log handler.

A no-op handler that silently discards
all log records. Useful for testing and
as a placeholder in handler chains.
"""

from __future__ import annotations

from typing import Optional

from ..models import LogEntry
from .base import LogHandler


class NullHandler(LogHandler):
    """
    Null log handler.

    Discards all log records without
    any output. Useful for:
    - Testing environments
    - Disabling specific loggers
    - Placeholder in handler chains

    Usage:
        handler = NullHandler()
        await handler.emit(log_entry)  # No-op
    """

    def __init__(
        self,
        name: Optional[str] = None,
    ) -> None:
        """Initialize null handler."""

        super().__init__(name=name)

    async def emit(
        self,
        record: LogEntry,
    ) -> None:
        """
        Emit a log record (no-op).

        Args:
            record: LogEntry to discard.
        """

        self._emit_count += 1
