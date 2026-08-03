"""
Logger factory.

Provides the Logger class and a logger
registry for creating and managing
named loggers throughout the application.

Supports both sync callable handlers and
async LogHandler instances. When async
handlers are registered and an event loop
is running, their emit() coroutines are
scheduled automatically.

All loggers share the same configuration
and formatter, ensuring consistent
output across the platform.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from .config import LoggingConfig
from .constants import DEFAULT_LOGGER, LOG_LEVEL_NUMERIC
from .context import get_context
from .exceptions import HandlerError
from .formatter import JsonFormatter, TextFormatter, get_formatter
from .models import LogEntry
from .record import build_record


class Logger:
    """
    Structured logger.

    Provides level-based logging methods
    (debug, info, warning, error, critical)
    that produce structured LogEntry
    objects and output them via configured
    handlers.

    Features:
    - Automatic context injection (trace_id, span_id)
    - JSON and text output formats
    - Level filtering
    - Additional structured fields via **kwargs

    Usage:
        logger = Logger("strategy")
        logger.info("Order submitted", symbol="AAPL", order_id="123")
        logger.error("Order rejected", reason="insufficient_balance")
    """

    def __init__(
        self,
        name: str = DEFAULT_LOGGER,
        config: Optional[LoggingConfig] = None,
    ) -> None:
        """
        Initialize logger.

        Args:
            name: Logger name.
            config: Logging configuration.
        """

        self._name = name
        self._config = config or LoggingConfig()
        self._formatter = get_formatter(self._config.format)
        self._handlers: List[Any] = []
        self._log_count: int = 0
        self._error_count: int = 0

    @property
    def name(
        self,
    ) -> str:
        """Get logger name."""
        return self._name

    @property
    def config(
        self,
    ) -> LoggingConfig:
        """Get logging config."""
        return self._config

    @property
    def log_count(
        self,
    ) -> int:
        """Get total log count."""
        return self._log_count

    @property
    def error_count(
        self,
    ) -> int:
        """Get total error count."""
        return self._error_count

    def _should_log(
        self,
        level: str,
    ) -> bool:
        """
        Check if a level should be logged.

        Args:
            level: Log level to check.

        Returns:
            True if level meets threshold.
        """

        level_num = LOG_LEVEL_NUMERIC.get(level.upper(), 20)
        return level_num >= self._config.level_numeric

    def _emit(
        self,
        level: str,
        message: str,
        **fields: Any,
    ) -> Optional[LogEntry]:
        """
        Internal log emission.

        Handles both sync callable handlers and
        async LogHandler instances. For async
        handlers, schedules emit() if an event
        loop is running, otherwise skips.

        Args:
            level: Log level.
            message: Log message.
            **fields: Additional fields.

        Returns:
            LogEntry if logged, None if filtered.
        """

        if not self._should_log(level):
            return None

        record = build_record(
            level=level,
            logger=self._name,
            message=message,
            **fields,
        )

        self._log_count += 1

        if level.upper() in ("ERROR", "CRITICAL"):
            self._error_count += 1

        # Format and output to console (default)
        if not self._handlers:
            try:
                output = self._formatter.format(record)
                print(output)
            except Exception:
                pass

        # Dispatch to handlers
        for handler in self._handlers:
            self._dispatch_handler(handler, record)

        return record

    def _dispatch_handler(
        self,
        handler: Any,
        record: LogEntry,
    ) -> None:
        """
        Dispatch a record to a handler.

        Supports three handler types:
        1. LogHandler instances with async emit()
        2. Sync callables
        3. LogHandler instances with sync __call__

        Args:
            handler: Handler instance or callable.
            record: LogEntry to dispatch.
        """

        try:
            # Check if it's a LogHandler with async emit
            if hasattr(handler, "emit"):
                emit_result = handler.emit(record)
                if asyncio.iscoroutine(emit_result):
                    # Try to schedule in running event loop
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(emit_result)
                    except RuntimeError:
                        # No running loop, run synchronously
                        asyncio.run(emit_result)
            else:
                # Sync callable
                handler(record)
        except Exception:
            pass

    async def _aemit(
        self,
        level: str,
        message: str,
        **fields: Any,
    ) -> Optional[LogEntry]:
        """
        Async log emission.

        Awaits async handlers directly instead
        of scheduling them as tasks.

        Args:
            level: Log level.
            message: Log message.
            **fields: Additional fields.

        Returns:
            LogEntry if logged, None if filtered.
        """

        if not self._should_log(level):
            return None

        record = build_record(
            level=level,
            logger=self._name,
            message=message,
            **fields,
        )

        self._log_count += 1

        if level.upper() in ("ERROR", "CRITICAL"):
            self._error_count += 1

        # Format and output to console (default)
        if not self._handlers:
            try:
                output = self._formatter.format(record)
                print(output)
            except Exception:
                pass

        # Dispatch to handlers (await async ones)
        for handler in self._handlers:
            try:
                if hasattr(handler, "emit"):
                    result = handler.emit(record)
                    if asyncio.iscoroutine(result):
                        await result
                else:
                    handler(record)
            except Exception:
                pass

        return record

    # === Public Logging Methods ===

    def debug(
        self,
        message: str,
        **fields: Any,
    ) -> Optional[LogEntry]:
        """
        Log at DEBUG level.

        Args:
            message: Log message.
            **fields: Additional structured fields.
        """

        return self._emit("DEBUG", message, **fields)

    def info(
        self,
        message: str,
        **fields: Any,
    ) -> Optional[LogEntry]:
        """
        Log at INFO level.

        Args:
            message: Log message.
            **fields: Additional structured fields.
        """

        return self._emit("INFO", message, **fields)

    def warning(
        self,
        message: str,
        **fields: Any,
    ) -> Optional[LogEntry]:
        """
        Log at WARNING level.

        Args:
            message: Log message.
            **fields: Additional structured fields.
        """

        return self._emit("WARNING", message, **fields)

    def error(
        self,
        message: str,
        **fields: Any,
    ) -> Optional[LogEntry]:
        """
        Log at ERROR level.

        Args:
            message: Log message.
            **fields: Additional structured fields.
        """

        return self._emit("ERROR", message, **fields)

    def critical(
        self,
        message: str,
        **fields: Any,
    ) -> Optional[LogEntry]:
        """
        Log at CRITICAL level.

        Args:
            message: Log message.
            **fields: Additional structured fields.
        """

        return self._emit("CRITICAL", message, **fields)

    # === Async Logging Methods ===

    async def ainfo(
        self,
        message: str,
        **fields: Any,
    ) -> Optional[LogEntry]:
        """
        Async log at INFO level.

        Awaits async handlers directly.

        Args:
            message: Log message.
            **fields: Additional structured fields.
        """

        return await self._aemit("INFO", message, **fields)

    async def adebug(
        self,
        message: str,
        **fields: Any,
    ) -> Optional[LogEntry]:
        """Async log at DEBUG level."""

        return await self._aemit("DEBUG", message, **fields)

    async def awarning(
        self,
        message: str,
        **fields: Any,
    ) -> Optional[LogEntry]:
        """Async log at WARNING level."""

        return await self._aemit("WARNING", message, **fields)

    async def aerror(
        self,
        message: str,
        **fields: Any,
    ) -> Optional[LogEntry]:
        """Async log at ERROR level."""

        return await self._aemit("ERROR", message, **fields)

    async def acritical(
        self,
        message: str,
        **fields: Any,
    ) -> Optional[LogEntry]:
        """Async log at CRITICAL level."""

        return await self._aemit("CRITICAL", message, **fields)

    # === Handler Management ===

    def add_handler(
        self,
        handler: Any,
    ) -> None:
        """
        Add a log handler.

        Args:
            handler: Callable that accepts LogEntry.
        """

        self._handlers.append(handler)

    def remove_handler(
        self,
        handler: Any,
    ) -> None:
        """
        Remove a log handler.

        Args:
            handler: Handler to remove.
        """

        self._handlers.remove(handler)

    # === Status ===

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """
        Get logger status.

        Returns:
            Status dictionary.
        """

        return {
            "name": self._name,
            "level": self._config.level,
            "format": self._config.format,
            "log_count": self._log_count,
            "error_count": self._error_count,
            "handlers": len(self._handlers),
        }


# === Logger Registry ===

_loggers: Dict[str, Logger] = {}


def get_logger(
    name: str = DEFAULT_LOGGER,
    config: Optional[LoggingConfig] = None,
) -> Logger:
    """
    Get or create a named logger.

    Loggers are cached by name. If a logger
    with the given name already exists, it
    is returned. Otherwise a new logger is
    created with the provided config.

    Args:
        name: Logger name.
        config: Optional config for new loggers.

    Returns:
        Logger instance.
    """

    if name not in _loggers:
        _loggers[name] = Logger(name=name, config=config)
    return _loggers[name]


def clear_loggers() -> None:
    """Clear all cached loggers."""

    _loggers.clear()
