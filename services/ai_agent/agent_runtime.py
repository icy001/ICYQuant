"""
Agent runtime configuration and execution environment.

Manages runtime lifecycle, concurrency control, resource limits,
and execution modes for AI agents.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from shared.exceptions import ICYQuantError, ConfigurationError

logger = logging.getLogger(__name__)


# ── Runtime Enums ──


class RuntimeMode(str, Enum):
    """Agent execution mode."""

    SYNC = "sync"           # Synchronous single-agent execution
    ASYNC = "async"         # Asynchronous background execution
    STREAMING = "streaming" # Streaming response execution
    BATCH = "batch"         # Batch processing mode


class RuntimeStatus(str, Enum):
    """Runtime lifecycle status."""

    INITIALIZED = "initialized"
    RUNNING = "running"
    IDLE = "idle"
    DRAINING = "draining"
    STOPPED = "stopped"
    ERROR = "error"


# ── Configuration ──


@dataclass
class RuntimeConfig:
    """Agent runtime configuration.

    Controls concurrency, timeouts, resource limits, and execution behavior.
    """

    # Concurrency
    max_concurrent_agents: int = 10
    max_concurrent_tasks: int = 50
    task_queue_size: int = 1000

    # Timeouts (seconds)
    agent_timeout: float = 300.0
    planning_timeout: float = 60.0
    reasoning_timeout: float = 120.0
    execution_timeout: float = 180.0
    idle_timeout: float = 600.0

    # Resource limits
    max_memory_mb: int = 512
    max_steps_per_plan: int = 100
    max_reasoning_depth: int = 10

    # Behavior
    enable_cancellation: bool = True
    enable_retry: bool = True
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    graceful_shutdown_timeout: float = 30.0

    # Monitoring
    enable_metrics: bool = True
    enable_telemetry: bool = True

    def validate(self) -> None:
        """Validate runtime configuration."""
        if self.max_concurrent_agents < 1:
            raise ConfigurationError("max_concurrent_agents must be >= 1")
        if self.max_concurrent_tasks < 1:
            raise ConfigurationError("max_concurrent_tasks must be >= 1")
        if self.agent_timeout <= 0:
            raise ConfigurationError("agent_timeout must be > 0")
        if self.max_steps_per_plan < 1:
            raise ConfigurationError("max_steps_per_plan must be >= 1")


# ── Agent Runtime ──


class AgentRuntime:
    """Unified agent runtime environment.

    Manages lifecycle, concurrency, and resource allocation for agent execution.

    Usage:
        runtime = AgentRuntime(config=RuntimeConfig())
        await runtime.initialize()
        await runtime.execute(agent_task)
        await runtime.shutdown()
    """

    def __init__(self, config: Optional[RuntimeConfig] = None) -> None:
        self.config = config or RuntimeConfig()
        self.config.validate()
        self.runtime_id: str = uuid4().hex[:16]
        self.status: RuntimeStatus = RuntimeStatus.INITIALIZED
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._started_at: Optional[float] = None
        self._stats: Dict[str, Any] = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "cancelled_executions": 0,
        }

        logger.info(f"AgentRuntime [{self.runtime_id}] created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the runtime environment."""
        if self.status != RuntimeStatus.INITIALIZED:
            logger.warning(f"Runtime [{self.runtime_id}] already initialized")
            return

        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_agents)
        self._started_at = asyncio.get_event_loop().time()
        self.status = RuntimeStatus.IDLE
        logger.info(
            f"AgentRuntime [{self.runtime_id}] initialized",
            extra={
                "max_concurrent_agents": self.config.max_concurrent_agents,
                "max_concurrent_tasks": self.config.max_concurrent_tasks,
                "agent_timeout": self.config.agent_timeout,
            },
        )

    async def execute(
        self,
        task_id: str,
        coro: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute an agent task with concurrency control and timeout."""
        if self.status in (RuntimeStatus.DRAINING, RuntimeStatus.STOPPED):
            raise ICYQuantError(f"Runtime [{self.runtime_id}] is not accepting tasks")

        if self._semaphore is None:
            raise ConfigurationError("Runtime not initialized. Call initialize() first")

        async with self._semaphore:
            self.status = RuntimeStatus.RUNNING
            self._stats["total_executions"] += 1

            try:
                result = await asyncio.wait_for(
                    coro(*args, **kwargs),
                    timeout=self.config.agent_timeout,
                )
                self._stats["successful_executions"] += 1
                return result
            except asyncio.TimeoutError:
                self._stats["failed_executions"] += 1
                logger.error(f"Task [{task_id}] timed out after {self.config.agent_timeout}s")
                raise
            except asyncio.CancelledError:
                self._stats["cancelled_executions"] += 1
                logger.warning(f"Task [{task_id}] was cancelled")
                raise
            except Exception:
                self._stats["failed_executions"] += 1
                logger.exception(f"Task [{task_id}] failed")
                raise
            finally:
                if not self.active_tasks:
                    self.status = RuntimeStatus.IDLE

    async def shutdown(self) -> None:
        """Gracefully shut down the runtime."""
        logger.info(f"AgentRuntime [{self.runtime_id}] shutting down...")
        self.status = RuntimeStatus.DRAINING

        # Cancel remaining active tasks
        for task_id, task in list(self.active_tasks.items()):
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled active task: {task_id}")

        # Wait for tasks to complete with timeout
        if self.active_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.active_tasks.values(), return_exceptions=True),
                    timeout=self.config.graceful_shutdown_timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    f"Shutdown timeout exceeded after {self.config.graceful_shutdown_timeout}s"
                )

        self.active_tasks.clear()
        self.status = RuntimeStatus.STOPPED
        logger.info(
            f"AgentRuntime [{self.runtime_id}] shut down",
            extra={"stats": self._stats},
        )

    # ── Status ──

    def get_status(self) -> Dict[str, Any]:
        """Get runtime status and statistics."""
        return {
            "runtime_id": self.runtime_id,
            "status": self.status.value,
            "active_task_count": len(self.active_tasks),
            "config": {
                "max_concurrent_agents": self.config.max_concurrent_agents,
                "max_concurrent_tasks": self.config.max_concurrent_tasks,
                "agent_timeout": self.config.agent_timeout,
            },
            "stats": dict(self._stats),
        }

    # ── Health ──

    def is_healthy(self) -> bool:
        """Check if runtime is healthy and accepting tasks."""
        return self.status in (RuntimeStatus.RUNNING, RuntimeStatus.IDLE)
