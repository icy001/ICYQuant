"""
ICYQuant Agent Runtime — multi-agent execution environment.

Manages the lifecycle, concurrency, resource allocation, and event loop
for all AI agents in the collaborative quant research system.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
    max_concurrent_agents: int = 20
    max_concurrent_tasks: int = 50
    task_timeout_seconds: int = 600
    agent_startup_timeout: int = 30
    grace_period_seconds: int = 30
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeStats:
    state: RuntimeState
    active_agents: int
    active_tasks: int
    completed_tasks: int
    failed_tasks: int
    uptime_seconds: float


class AgentRuntime:
    """Multi-agent execution environment.

    Responsibilities:
        - Agent lifecycle management (start/stop/pause/resume)
        - Concurrency control via semaphores
        - Task scheduling with timeout enforcement
        - Resource cleanup on shutdown
        - Health monitoring
    """

    def __init__(self, config: Optional[RuntimeConfig] = None) -> None:
        self._config = config or RuntimeConfig()
        self._state = RuntimeState.CREATED
        self._agent_semaphore: Optional[asyncio.Semaphore] = None
        self._task_semaphore: Optional[asyncio.Semaphore] = None
        self._active_tasks: set[asyncio.Task] = set()
        self._completed = 0
        self._failed = 0
        self._started_at: Optional[float] = None
        self._agent_count = 0

    async def start(self) -> None:
        self._state = RuntimeState.STARTING
        self._agent_semaphore = asyncio.Semaphore(self._config.max_concurrent_agents)
        self._task_semaphore = asyncio.Semaphore(self._config.max_concurrent_tasks)
        self._started_at = asyncio.get_event_loop().time()
        self._state = RuntimeState.RUNNING
        logger.info("Agent runtime started (agents=%d, tasks=%d)",
                     self._config.max_concurrent_agents, self._config.max_concurrent_tasks)

    async def stop(self) -> None:
        self._state = RuntimeState.STOPPING
        if self._active_tasks:
            await asyncio.gather(*self._active_tasks, return_exceptions=True)
        self._state = RuntimeState.STOPPED
        logger.info("Agent runtime stopped")

    async def pause(self) -> None:
        self._state = RuntimeState.PAUSING
        self._state = RuntimeState.PAUSED

    async def resume(self) -> None:
        if self._state == RuntimeState.PAUSED:
            self._state = RuntimeState.RUNNING

    async def spawn_agent(self, agent_factory: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Spawn a new agent instance with concurrency control."""
        if self._state != RuntimeState.RUNNING:
            raise RuntimeError(f"Cannot spawn agent in state {self._state}")
        if self._agent_semaphore is None:
            raise RuntimeError("Runtime not started")

        async with self._agent_semaphore:
            agent = agent_factory(*args, **kwargs)
            self._agent_count += 1
            return agent

    async def submit_task(self, coro: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Submit a task with timeout enforcement."""
        if self._state not in (RuntimeState.RUNNING, RuntimeState.PAUSED):
            raise RuntimeError(f"Cannot submit in state {self._state}")
        if self._task_semaphore is None:
            raise RuntimeError("Runtime not started")

        async with self._task_semaphore:
            try:
                result = await asyncio.wait_for(
                    coro(*args, **kwargs),
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
            active_agents=self._agent_count,
            active_tasks=len(self._active_tasks),
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
