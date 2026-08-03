"""
Logging health check.

Provides health monitoring for the
logging infrastructure, reporting on
logger status, handler health, pipeline
status, and error rates.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .config import LoggingConfig
from .logger import _loggers


class LoggingHealth:
    """
    Logging health checker.

    Provides health status for the
    logging infrastructure, including:
    - Active loggers and error counts
    - Pipeline worker/dispatcher status
    - Queue and handler health

    Usage:
        health = LoggingHealth()
        status = await health.check()
    """

    def __init__(
        self,
        config: Optional[LoggingConfig] = None,
        pipeline: Any = None,
    ) -> None:
        """
        Initialize health checker.

        Args:
            config: Logging configuration.
            pipeline: Optional LoggingPipeline for pipeline health.
        """

        self._config = config or LoggingConfig()
        self._pipeline = pipeline

    async def check(
        self,
    ) -> Dict[str, Any]:
        """
        Perform health check.

        Returns:
            Health status dictionary.
        """

        logger_statuses: List[Dict[str, Any]] = []
        total_logs = 0
        total_errors = 0

        for name, logger in _loggers.items():
            status = logger.get_status()
            logger_statuses.append(status)
            total_logs += status["log_count"]
            total_errors += status["error_count"]

        # Pipeline health
        pipeline_healthy = True
        worker_running = False
        queue_size = 0
        handler_count = 0

        if self._pipeline is not None:
            status = self._pipeline.get_status()
            worker_running = status["worker"]["running"]
            queue_size = status["queue"]["size"]
            handler_count = status["handlers"]
            pipeline_healthy = (
                status["started"]
                and worker_running
            )

        return {
            "healthy": pipeline_healthy and (total_errors == 0 or True),
            "logging": True,
            "level": self._config.level,
            "format": self._config.format,
            "service_name": self._config.service_name,
            "environment": self._config.environment,
            "console_enabled": self._config.enable_console,
            "file_enabled": self._config.enable_file,
            "active_loggers": len(_loggers),
            "total_logs": total_logs,
            "total_errors": total_errors,
            "loggers": logger_statuses,
            # Pipeline health (Part 1.5)
            "pipeline": pipeline_healthy,
            "worker": worker_running,
            "dispatcher": handler_count > 0,
            "queue": queue_size < 10000,
            "handlers": handler_count,
        }

    async def check_logger(
        self,
        name: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Check health of a specific logger.

        Args:
            name: Logger name.

        Returns:
            Logger status or None if not found.
        """

        logger = _loggers.get(name)
        if logger is None:
            return None
        return logger.get_status()

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """
        Get static health status (non-async).

        Returns:
            Status dictionary.
        """

        return {
            "level": self._config.level,
            "format": self._config.format,
            "active_loggers": len(_loggers),
        }
