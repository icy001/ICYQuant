"""
Base logging handler.

Defines the abstract base class for all
log handlers, providing the interface for
emitting, starting, and shutting down
log output destinations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from ..models import LogEntry


class LogHandler(ABC):
    """
    Abstract base class for log handlers.

    A handler receives LogEntry objects and
    outputs them to a specific destination
    (console, file, Kafka, Elasticsearch, etc.).

    Subclasses must implement the emit() method.
    The startup() and shutdown() methods provide
    lifecycle hooks for resource management.

    Usage:
        class MyHandler(LogHandler):
            async def emit(self, record: LogEntry) -> None:
                print(record.message)
    """

    def __init__(
        self,
        name: Optional[str] = None,
    ) -> None:
        """
        Initialize handler.

        Args:
            name: Optional handler name.
        """

        self._name = name or self.__class__.__name__
        self._started: bool = False
        self._emit_count: int = 0
        self._error_count: int = 0

    @property
    def name(
        self,
    ) -> str:
        """Get handler name."""
        return self._name

    @property
    def is_started(
        self,
    ) -> bool:
        """Check if handler is started."""
        return self._started

    @property
    def emit_count(
        self,
    ) -> int:
        """Get total emit count."""
        return self._emit_count

    @property
    def error_count(
        self,
    ) -> int:
        """Get total error count."""
        return self._error_count

    @abstractmethod
    async def emit(
        self,
        record: LogEntry,
    ) -> None:
        """
        Emit a log record.

        Args:
            record: LogEntry to emit.
        """

    async def startup(
        self,
    ) -> None:
        """Start the handler. Override for resource init."""

        self._started = True

    async def shutdown(
        self,
    ) -> None:
        """Shutdown the handler. Override for cleanup."""

        self._started = False

    def get_status(
        self,
    ) -> dict:
        """
        Get handler status.

        Returns:
            Status dictionary.
        """

        return {
            "name": self._name,
            "type": self.__class__.__name__,
            "started": self._started,
            "emit_count": self._emit_count,
            "error_count": self._error_count,
        }
