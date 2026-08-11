"""
Pre-Trade Risk Runtime — Runtime environment for the pre-trade pipeline.

Manages the execution lifecycle, concurrency control, and request
tracking for the Pre-Trade Risk Engine.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RuntimeStatus(str, Enum):
    """Pre-trade runtime operational status."""
    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    RECOVERING = "recovering"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class RuntimeConfig:
    """Pre-trade runtime configuration."""
    max_concurrent_evaluations: int = 100
    evaluation_timeout_seconds: float = 5.0
    queue_size: int = 1000
    heartbeat_interval_seconds: float = 5.0
    enable_metrics: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeState:
    """Current runtime state snapshot."""
    status: RuntimeStatus = RuntimeStatus.CREATED
    active_evaluations: int = 0
    queued_requests: int = 0
    completed_evaluations: int = 0
    rejected_evaluations: int = 0
    failed_evaluations: int = 0
    started_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    uptime_seconds: float = 0.0


class PreTradeRuntime:
    """
    Runtime environment for the Pre-Trade Risk Engine.

    Provides concurrency control, request queue management,
    heartbeat monitoring, and state tracking.

    Usage::

        runtime = PreTradeRuntime(config=RuntimeConfig())
        await runtime.initialize()
        await runtime.start()
    """

    def __init__(self, config: Optional[RuntimeConfig] = None) -> None:
        self._config = config or RuntimeConfig()
        self._state = RuntimeState()
        self._semaphore = asyncio.Semaphore(self._config.max_concurrent_evaluations)
        self._queue: list[asyncio.Task] = []
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    @property
    def status(self) -> RuntimeStatus:
        return self._state.status

    @property
    def config(self) -> RuntimeConfig:
        return self._config

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize the pre-trade runtime."""
        self._state.status = RuntimeStatus.INITIALIZING
        logger.info("PreTradeRuntime initializing...")
        self._state.status = RuntimeStatus.CREATED
        logger.info("PreTradeRuntime initialized.")

    async def start(self) -> None:
        """Start the runtime."""
        self._state.status = RuntimeStatus.RUNNING
        self._state.started_at = datetime.now(timezone.utc)
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("PreTradeRuntime started.")

    async def stop(self) -> None:
        """Stop the runtime gracefully."""
        self._state.status = RuntimeStatus.STOPPING
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        self._state.status = RuntimeStatus.STOPPED
        logger.info("PreTradeRuntime stopped.")

    async def pause(self) -> None:
        """Pause accepting new evaluations."""
        self._state.status = RuntimeStatus.PAUSED
        logger.info("PreTradeRuntime paused.")

    async def resume(self) -> None:
        """Resume accepting evaluations."""
        self._state.status = RuntimeStatus.RUNNING
        logger.info("PreTradeRuntime resumed.")

    # ---- Capacity Control ----

    async def acquire(self) -> bool:
        """Acquire an evaluation slot. Returns False if runtime is not running."""
        if self._state.status != RuntimeStatus.RUNNING:
            return False
        await self._semaphore.acquire()
        async with self._lock:
            self._state.active_evaluations += 1
        return True

    async def release(self, success: bool = True) -> None:
        """Release an evaluation slot."""
        self._semaphore.release()
        async with self._lock:
            self._state.active_evaluations = max(0, self._state.active_evaluations - 1)
            if success:
                self._state.completed_evaluations += 1
            else:
                self._state.failed_evaluations += 1

    async def record_rejection(self) -> None:
        """Record a rejected evaluation."""
        async with self._lock:
            self._state.rejected_evaluations += 1

    # ---- State Query ----

    def get_state(self) -> RuntimeState:
        """Get current runtime state."""
        state = self._state
        if state.started_at:
            state.uptime_seconds = (
                datetime.now(timezone.utc) - state.started_at
            ).total_seconds()
        return state

    async def health_check(self) -> dict[str, Any]:
        """Check runtime health."""
        state = self.get_state()
        return {
            "status": state.status.value,
            "active_evaluations": state.active_evaluations,
            "completed_evaluations": state.completed_evaluations,
            "rejected_evaluations": state.rejected_evaluations,
            "failed_evaluations": state.failed_evaluations,
            "uptime_seconds": state.uptime_seconds,
            "queue_depth": len(self._queue),
        }

    async def _heartbeat_loop(self) -> None:
        """Periodic heartbeat."""
        while True:
            try:
                await asyncio.sleep(self._config.heartbeat_interval_seconds)
                self._state.last_heartbeat = datetime.now(timezone.utc)
            except asyncio.CancelledError:
                break
