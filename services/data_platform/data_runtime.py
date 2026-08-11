"""
ICYQuant Unified Data Platform Runtime.

Commit 16 Part 1.5 — Manages the lifecycle, configuration, and status
of the unified data platform runtime environment.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DataPlatformRuntimeStatus(str, Enum):
    """Runtime operational status."""
    CREATED = "created"
    CONFIGURING = "configuring"
    CONFIGURED = "configured"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    DEGRADED = "degraded"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class DataPlatformRuntimeConfig:
    """Runtime configuration for the data platform."""
    max_workers: int = 64
    max_concurrent_requests: int = 10_000
    queue_size: int = 100_000
    request_timeout_seconds: float = 30.0
    graceful_shutdown_seconds: float = 30.0
    health_check_interval_seconds: float = 15.0
    metrics_export_interval_seconds: float = 60.0
    enable_profiling: bool = False
    enable_tracing: bool = True
    log_level: str = "INFO"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeInfo:
    """Information about the runtime environment."""
    status: DataPlatformRuntimeStatus = DataPlatformRuntimeStatus.CREATED
    started_at: Optional[datetime] = None
    uptime_seconds: float = 0.0
    worker_count: int = 0
    active_tasks: int = 0
    queued_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0


class DataPlatformRuntime:
    """Runtime manager for the unified data platform.

    Handles task scheduling, worker management, health monitoring,
    and graceful shutdown coordination across all platform subsystems.
    """

    def __init__(self, config: Optional[DataPlatformRuntimeConfig] = None) -> None:
        self._config = config or DataPlatformRuntimeConfig()
        self._status = DataPlatformRuntimeStatus.CREATED
        self._started_at: Optional[datetime] = None
        self._tasks: dict[str, asyncio.Task] = {}
        self._completed_count = 0
        self._failed_count = 0
        self._active_subsystems: set[str] = set()
        self._lock = asyncio.Lock()

    async def configure(self, **kwargs: Any) -> None:
        """Configure runtime parameters."""
        self._status = DataPlatformRuntimeStatus.CONFIGURING
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
        self._status = DataPlatformRuntimeStatus.CONFIGURED
        logger.info("DataPlatformRuntime configured: %s", self._config)

    async def initialize(self) -> None:
        """Initialize the runtime environment."""
        self._status = DataPlatformRuntimeStatus.INITIALIZING
        self._status = DataPlatformRuntimeStatus.READY
        logger.info("DataPlatformRuntime initialized")

    async def start(self) -> None:
        """Start the runtime."""
        self._status = DataPlatformRuntimeStatus.RUNNING
        self._started_at = datetime.now(timezone.utc)
        logger.info("DataPlatformRuntime started")

    async def stop(self) -> None:
        """Stop the runtime gracefully."""
        self._status = DataPlatformRuntimeStatus.STOPPING
        timeout = self._config.graceful_shutdown_seconds

        async with self._lock:
            remaining = list(self._tasks.values())
            if remaining:
                done, pending = await asyncio.wait(
                    remaining, timeout=timeout,
                )
                for task in pending:
                    task.cancel()

        self._status = DataPlatformRuntimeStatus.STOPPED
        logger.info("DataPlatformRuntime stopped (completed=%d, failed=%d)",
                    self._completed_count, self._failed_count)

    def register_subsystem(self, name: str) -> None:
        """Register an active subsystem."""
        self._active_subsystems.add(name)

    def unregister_subsystem(self, name: str) -> None:
        """Unregister a subsystem."""
        self._active_subsystems.discard(name)

    async def spawn_task(self, task_id: str, coro) -> asyncio.Task:
        """Spawn a tracked async task."""
        async with self._lock:
            task = asyncio.create_task(self._wrap_task(task_id, coro))
            self._tasks[task_id] = task
            return task

    async def _wrap_task(self, task_id: str, coro) -> Any:
        try:
            result = await coro
            self._completed_count += 1
            return result
        except Exception:
            self._failed_count += 1
            logger.exception("Task %s failed", task_id)
            raise
        finally:
            async with self._lock:
                self._tasks.pop(task_id, None)

    @property
    def status(self) -> DataPlatformRuntimeStatus:
        return self._status

    @property
    def config(self) -> DataPlatformRuntimeConfig:
        return self._config

    @property
    def is_running(self) -> bool:
        return self._status == DataPlatformRuntimeStatus.RUNNING

    def info(self) -> RuntimeInfo:
        uptime = 0.0
        if self._started_at:
            uptime = (datetime.now(timezone.utc) - self._started_at).total_seconds()
        return RuntimeInfo(
            status=self._status,
            started_at=self._started_at,
            uptime_seconds=uptime,
            worker_count=self._config.max_workers,
            active_tasks=len(self._tasks),
            completed_tasks=self._completed_count,
            failed_tasks=self._failed_count,
        )
