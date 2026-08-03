"""
Logging service.

Unified entry point for the logging
platform, coordinating the logger
manager, async pipeline, and lifecycle
management.

Provides a single interface for:
- Starting/stopping the logging system
- Submitting log records
- Querying health and diagnostics
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from .context.manager import ContextManager
from .context.masker import DataMasker
from .context.filters import ContextFilter
from .dispatcher import LogDispatcher
from .handlers import LogHandler, NullHandler, ConsoleHandler
from .manager import LoggerManager
from .metrics import LoggingMetrics
from .models import LogEntry
from .pipeline import LoggingPipeline
from .queue import LogQueue
from .worker import LoggingWorker
from .batch import BatchCollector
from .config import LoggingConfig


class LoggingService:
    """
    Unified logging service.

    Combines logger management, async pipeline,
    and lifecycle management into a single
    service component.

    Features:
    - Centralized logger management
    - Async log pipeline with batching
    - Context-aware logging
    - Sensitive data masking
    - Metrics tracking
    - Health monitoring
    - Graceful shutdown

    Usage:
        service = LoggingService(config=LoggingConfig(level="DEBUG"))
        service.add_handler(ConsoleHandler())
        await service.startup()

        logger = service.get_logger("strategy")
        logger.info("Order submitted", symbol="AAPL")

        await service.shutdown()
    """

    def __init__(
        self,
        config: Optional[LoggingConfig] = None,
        handlers: Optional[List[LogHandler]] = None,
        queue_size: int = 10000,
        batch_size: int = 100,
        flush_interval: float = 1.0,
        enable_masking: bool = True,
    ) -> None:
        """
        Initialize logging service.

        Args:
            config: Logging configuration.
            handlers: List of log handlers.
            queue_size: Async queue max size.
            batch_size: Max records per batch.
            flush_interval: Batch flush timeout.
            enable_masking: Whether to mask sensitive data.
        """

        self._config = config or LoggingConfig()
        self._handlers: List[LogHandler] = handlers or []
        self._metrics = LoggingMetrics()
        self._masker = DataMasker() if enable_masking else None

        # Logger manager
        self._manager = LoggerManager(config=self._config)

        # Async pipeline
        self._pipeline = LoggingPipeline(
            handlers=self._handlers,
            queue_size=queue_size,
            batch_size=batch_size,
            flush_interval=flush_interval,
        )

        # Context filter for enrichment
        self._context_filter = ContextFilter(
            service=self._config.service_name,
            environment=self._config.environment,
        )

        self._started: bool = False

    @property
    def config(
        self,
    ) -> LoggingConfig:
        """Get logging config."""
        return self._config

    @property
    def manager(
        self,
    ) -> LoggerManager:
        """Get logger manager."""
        return self._manager

    @property
    def pipeline(
        self,
    ) -> LoggingPipeline:
        """Get logging pipeline."""
        return self._pipeline

    @property
    def metrics(
        self,
    ) -> LoggingMetrics:
        """Get pipeline metrics."""
        return self._metrics

    @property
    def is_started(
        self,
    ) -> bool:
        """Check if service is started."""
        return self._started

    def add_handler(
        self,
        handler: LogHandler,
    ) -> None:
        """
        Add a log handler.

        Args:
            handler: Handler to add.
        """

        self._handlers.append(handler)
        self._pipeline.add_handler(handler)
        self._manager.add_handler(handler)

    def get_logger(
        self,
        name: str,
    ):
        """Get a named logger."""

        return self._manager.get_logger(name)

    async def log(
        self,
        record: LogEntry,
    ) -> bool:
        """
        Submit a log record to the async pipeline.

        Applies context enrichment and masking
        before queueing.

        Args:
            record: LogEntry to log.

        Returns:
            True if accepted, False if dropped.
        """

        # Enrich with context
        self._context_filter.enrich(record)

        # Mask sensitive fields
        if self._masker is not None:
            record.fields = self._masker.mask(record.fields)

        # Submit to pipeline
        return await self._pipeline.log(record)

    async def startup(
        self,
    ) -> None:
        """Start the logging service."""

        if self._started:
            return

        # Start manager handlers
        await self._manager.startup()

        # Start pipeline
        await self._pipeline.start()

        self._started = True

    async def shutdown(
        self,
    ) -> None:
        """
        Shutdown the logging service.

        Ensures graceful shutdown:
        1. Stop accepting new logs
        2. Flush remaining queue
        3. Close all handlers
        """

        if not self._started:
            return

        # Stop pipeline (flushes queue)
        await self._pipeline.stop()

        # Shutdown manager handlers
        await self._manager.shutdown()

        self._started = False

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """
        Get service status.

        Returns:
            Status dictionary.
        """

        return {
            "started": self._started,
            "config": self._config.to_dict(),
            "pipeline": self._pipeline.get_status(),
            "metrics": self._metrics.to_dict(),
            "handlers": len(self._handlers),
            "loggers": self._manager.logger_count,
            "masking_enabled": self._masker is not None,
        }
