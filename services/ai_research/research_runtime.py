"""
ICYQuant Research Runtime — execution environment for AI research workloads.

Manages lifecycle, resource allocation, concurrency control, and runtime
configuration for all research components.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class RuntimeState(str, Enum):
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    PAUSING = "pausing"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class RuntimeConfig:
    max_concurrency: int = 10
    task_timeout_seconds: int = 300
    knowledge_timeout_seconds: int = 60
    report_timeout_seconds: int = 120
    grace_period_seconds: int = 30
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeStats:
    state: RuntimeState
    active_tasks: int
    completed_tasks: int
    failed_tasks: int
    uptime_seconds: float


class ResearchRuntime:
    """Manages the execution environment for AI research workloads.

    Responsibilities:
        - Lifecycle management (start/stop/pause/resume)
        - Concurrency control via semaphore
        - Task scheduling with timeout enforcement
        - Resource cleanup on shutdown
    """

    def __init__(self, config: Optional[RuntimeConfig] = None) -> None:
        self._config = config or RuntimeConfig()
        self._state = RuntimeState.CREATED
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._tasks: set[asyncio.Task] = set()
        self._completed = 0
        self._failed = 0
        self._started_at: Optional[float] = None

    async def start(self) -> None:
        """Start the runtime and initialize resources."""
        self._state = RuntimeState.STARTING
        self._semaphore = asyncio.Semaphore(self._config.max_concurrency)
        self._started_at = asyncio.get_event_loop().time()
        self._state = RuntimeState.RUNNING
        logger.info("Research runtime started (max_concurrency=%d)", self._config.max_concurrency)

    async def stop(self) -> None:
        """Gracefully shutdown the runtime, waiting for in-flight tasks."""
        self._state = RuntimeState.STOPPING
        if self._tasks:
            logger.info("Waiting for %d in-flight tasks to complete...", len(self._tasks))
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._state = RuntimeState.STOPPED
        logger.info("Research runtime stopped")

    async def pause(self) -> None:
        """Pause task scheduling (in-flight tasks continue)."""
        self._state = RuntimeState.PAUSING
        self._state = RuntimeState.PAUSED
        logger.info("Research runtime paused")

    async def resume(self) -> None:
        """Resume task scheduling."""
        if self._state == RuntimeState.PAUSED:
            self._state = RuntimeState.RUNNING
            logger.info("Research runtime resumed")

    async def submit(
        self,
        coro_func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Submit a coroutine for execution with concurrency control.

        Returns the coroutine result. Raises TimeoutError if the task
        exceeds the configured timeout.
        """
        if self._state not in (RuntimeState.RUNNING, RuntimeState.PAUSED):
            raise RuntimeError(f"Cannot submit task in state {self._state}")

        if self._semaphore is None:
            raise RuntimeError("Runtime not started")

        async with self._semaphore:
            try:
                result = await asyncio.wait_for(
                    coro_func(*args, **kwargs),
                    timeout=self._config.task_timeout_seconds,
                )
                self._completed += 1
                return result
            except Exception:
                self._failed += 1
                raise

    @property
    def stats(self) -> RuntimeStats:
        uptime = 0.0
        if self._started_at is not None:
            uptime = asyncio.get_event_loop().time() - self._started_at
        return RuntimeStats(
            state=self._state,
            active_tasks=len(self._tasks),
            completed_tasks=self._completed,
            failed_tasks=self._failed,
            uptime_seconds=uptime,
        )

    @property
    def state(self) -> RuntimeState:
        return self._state

    @property
    def is_ready(self) -> bool:
        return self._state == RuntimeState.RUNNING
