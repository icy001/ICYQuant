"""
Logger manager.

Provides centralized management of
named loggers, handler registration,
and filter configuration across the
application.

The LoggerManager acts as a singleton
registry, ensuring consistent logger
configuration throughout the platform.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .config import LoggingConfig
from .filters import LogFilter
from .handlers import LogHandler, NullHandler
from .logger import Logger, _loggers


class LoggerManager:
    """
    Centralized logger manager.

    Manages named logger instances, their
    handlers, and filters. Provides a
    single point of configuration for
    the entire logging infrastructure.

    Features:
    - Named logger registry
    - Shared handler attachment
    - Filter pipeline configuration
    - Level management
    - Health monitoring

    Usage:
        manager = LoggerManager(config=LoggingConfig(level="DEBUG"))
        manager.add_handler(ConsoleHandler())
        logger = manager.get_logger("strategy")
        logger.info("Order submitted")
    """

    def __init__(
        self,
        config: Optional[LoggingConfig] = None,
    ) -> None:
        """
        Initialize logger manager.

        Args:
            config: Logging configuration.
        """

        self._config = config or LoggingConfig()
        self._loggers: Dict[str, Logger] = {}
        self._default_handlers: List[LogHandler] = []
        self._filters: List[LogFilter] = []

    @property
    def config(
        self,
    ) -> LoggingConfig:
        """Get logging configuration."""
        return self._config

    @property
    def handlers(
        self,
    ) -> List[LogHandler]:
        """Get all registered handlers."""
        return self._default_handlers

    @property
    def filters(
        self,
    ) -> List[LogFilter]:
        """Get all registered filters."""
        return self._filters

    @property
    def logger_count(
        self,
    ) -> int:
        """Get number of managed loggers."""
        return len(self._loggers)

    def get_logger(
        self,
        name: str,
    ) -> Logger:
        """
        Get or create a named logger.

        Creates a new logger if one doesn't
        exist, attaching all default handlers
        and filters.

        Args:
            name: Logger name.

        Returns:
            Logger instance.
        """

        if name not in self._loggers:
            logger = Logger(
                name=name,
                config=self._config,
            )
            # Attach default handlers
            for handler in self._default_handlers:
                logger.add_handler(handler)
            self._loggers[name] = logger
            # Also register in global registry
            _loggers[name] = logger

        return self._loggers[name]

    def add_handler(
        self,
        handler: LogHandler,
    ) -> None:
        """
        Add a handler to all loggers.

        The handler is attached to all existing
        loggers and will be attached to any
        new loggers created via get_logger().

        Args:
            handler: Handler to add.
        """

        self._default_handlers.append(handler)
        for logger in self._loggers.values():
            logger.add_handler(handler)

    def remove_handler(
        self,
        handler: LogHandler,
    ) -> None:
        """
        Remove a handler from all loggers.

        Args:
            handler: Handler to remove.
        """

        if handler in self._default_handlers:
            self._default_handlers.remove(handler)
        for logger in self._loggers.values():
            logger.remove_handler(handler)

    def add_filter(
        self,
        filter_obj: LogFilter,
    ) -> None:
        """
        Add a log filter.

        Args:
            filter_obj: Filter to add.
        """

        self._filters.append(filter_obj)

    def remove_filter(
        self,
        filter_obj: LogFilter,
    ) -> None:
        """
        Remove a log filter.

        Args:
            filter_obj: Filter to remove.
        """

        if filter_obj in self._filters:
            self._filters.remove(filter_obj)

    def set_level(
        self,
        level: str,
    ) -> None:
        """
        Set log level for all loggers.

        Args:
            level: Log level (DEBUG, INFO, etc.).
        """

        self._config.level = level.upper()
        for logger in self._loggers.values():
            logger._config.level = level.upper()

    async def startup(
        self,
    ) -> None:
        """Start all handlers."""

        for handler in self._default_handlers:
            await handler.startup()

    async def shutdown(
        self,
    ) -> None:
        """Shutdown all handlers."""

        for handler in self._default_handlers:
            await handler.shutdown()

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """
        Get manager status.

        Returns:
            Status dictionary.
        """

        logger_statuses: List[Dict[str, Any]] = []
        total_logs = 0
        total_errors = 0

        for name, logger in self._loggers.items():
            status = logger.get_status()
            logger_statuses.append(status)
            total_logs += status["log_count"]
            total_errors += status["error_count"]

        handler_statuses = [
            h.get_status() for h in self._default_handlers
        ]

        return {
            "config": self._config.to_dict(),
            "logger_count": len(self._loggers),
            "handler_count": len(self._default_handlers),
            "filter_count": len(self._filters),
            "total_logs": total_logs,
            "total_errors": total_errors,
            "loggers": logger_statuses,
            "handlers": handler_statuses,
        }

    def clear(
        self,
    ) -> None:
        """Clear all loggers and handlers."""

        self._loggers.clear()
        self._default_handlers.clear()
        self._filters.clear()
