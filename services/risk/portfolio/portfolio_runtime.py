"""
Portfolio Runtime — Runtime environment for the portfolio risk pipeline.

Manages the execution lifecycle, concurrency control, state persistence,
and heartbeat for continuous portfolio monitoring.
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
    """Portfolio runtime status."""
    CREATED = "CREATED"
    INITIALIZING = "INITIALIZING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    RECOVERING = "RECOVERING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


@dataclass
class PortfolioRuntimeConfig:
    """Configuration for portfolio runtime."""
    max_concurrent_evaluations: int = 50
    evaluation_timeout_seconds: float = 30.0
    heartbeat_interval_seconds: float = 5.0
    snapshot_interval_seconds: float = 1.0
    enable_persistence: bool = True
    auto_recovery: bool = True
    max_recovery_attempts: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeState:
    """Current state of the portfolio runtime."""
    status: RuntimeStatus = RuntimeStatus.CREATED
    evaluations_active: int = 0
    evaluations_completed: int = 0
    evaluations_failed: int = 0
    snapshots_taken: int = 0
    started_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    last_snapshot_at: Optional[datetime] = None
    uptime_seconds: float = 0.0
    recovery_attempts: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class PortfolioRuntime:
    """
    Runtime environment for the portfolio risk pipeline.

    Manages execution lifecycle, concurrency, state persistence,
    and periodic heartbeats for continuous portfolio monitoring.

    Usage::

        runtime = PortfolioRuntime(config=PortfolioRuntimeConfig())
        await runtime.initialize()
        await runtime.start()
        state = runtime.get_state()
    """

    def __init__(self, config: Optional[PortfolioRuntimeConfig] = None) -> None:
        self._config = config or PortfolioRuntimeConfig()
        self._state = RuntimeState()
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._snapshot_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    @property
    def status(self) -> RuntimeStatus:
        return self._state.status

    @property
    def config(self) -> PortfolioRuntimeConfig:
        return self._config

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize the portfolio runtime."""
        self._state.status = RuntimeStatus.INITIALIZING
        logger.info("PortfolioRuntime initializing...")
        self._state.status = RuntimeStatus.CREATED
        logger.info("PortfolioRuntime initialized.")

    async def start(self) -> None:
        """Start the portfolio runtime and background tasks."""
        self._state.status = RuntimeStatus.RUNNING
        self._state.started_at = datetime.now(timezone.utc)
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        if self._config.enable_persistence:
            self._snapshot_task = asyncio.create_task(self._snapshot_loop())
        logger.info("PortfolioRuntime started.")

    async def stop(self) -> None:
        """Stop the portfolio runtime and cancel background tasks."""
        self._state.status = RuntimeStatus.STOPPING
        for task in [self._heartbeat_task, self._snapshot_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._heartbeat_task = None
        self._snapshot_task = None
        self._state.status = RuntimeStatus.STOPPED
        logger.info("PortfolioRuntime stopped.")

    async def pause(self) -> None:
        """Pause evaluations."""
        self._state.status = RuntimeStatus.PAUSED
        logger.info("PortfolioRuntime paused.")

    async def resume(self) -> None:
        """Resume evaluations."""
        self._state.status = RuntimeStatus.RUNNING
        logger.info("PortfolioRuntime resumed.")

    async def recover(self) -> None:
        """Attempt runtime recovery."""
        if self._state.recovery_attempts >= self._config.max_recovery_attempts:
            self._state.status = RuntimeStatus.ERROR
            logger.error("PortfolioRuntime: max recovery attempts exceeded.")
            return

        self._state.status = RuntimeStatus.RECOVERING
        self._state.recovery_attempts += 1
        self._state.evaluations_failed = 0
        self._state.status = RuntimeStatus.RUNNING
        logger.info(f"PortfolioRuntime recovered (attempt {self._state.recovery_attempts}).")

    # ---- State ----

    def get_state(self) -> RuntimeState:
        """Get current runtime state."""
        if self._state.started_at:
            self._state.uptime_seconds = (
                datetime.now(timezone.utc) - self._state.started_at
            ).total_seconds()
        return self._state

    async def record_evaluation_start(self) -> None:
        """Record the start of an evaluation."""
        async with self._lock:
            self._state.evaluations_active += 1

    async def record_evaluation_complete(self, success: bool = True) -> None:
        """Record the completion of an evaluation."""
        async with self._lock:
            self._state.evaluations_active = max(0, self._state.evaluations_active - 1)
            if success:
                self._state.evaluations_completed += 1
            else:
                self._state.evaluations_failed += 1

    async def record_snapshot(self) -> None:
        """Record that a snapshot was taken."""
        async with self._lock:
            self._state.snapshots_taken += 1
            self._state.last_snapshot_at = datetime.now(timezone.utc)

    # ---- Persistence ----

    async def save_snapshot(self) -> dict[str, Any]:
        """Save current runtime state as a snapshot."""
        state = self.get_state()
        return {
            "status": state.status.value,
            "evaluations_active": state.evaluations_active,
            "evaluations_completed": state.evaluations_completed,
            "evaluations_failed": state.evaluations_failed,
            "snapshots_taken": state.snapshots_taken,
            "uptime_seconds": state.uptime_seconds,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def restore_snapshot(self, snapshot: dict[str, Any]) -> None:
        """Restore runtime state from a snapshot."""
        status_str = snapshot.get("status", "CREATED")
        try:
            self._state.status = RuntimeStatus(status_str)
        except ValueError:
            self._state.status = RuntimeStatus.CREATED
        self._state.evaluations_completed = snapshot.get("evaluations_completed", 0)
        self._state.evaluations_failed = snapshot.get("evaluations_failed", 0)
        self._state.snapshots_taken = snapshot.get("snapshots_taken", 0)
        logger.info("PortfolioRuntime restored from snapshot.")

    # ---- Internal ----

    async def _heartbeat_loop(self) -> None:
        """Periodic heartbeat task."""
        while True:
            try:
                await asyncio.sleep(self._config.heartbeat_interval_seconds)
                self._state.last_heartbeat = datetime.now(timezone.utc)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

    async def _snapshot_loop(self) -> None:
        """Periodic snapshot persistence task."""
        while True:
            try:
                await asyncio.sleep(self._config.snapshot_interval_seconds)
                await self.save_snapshot()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Snapshot error: {e}")

    async def health_check(self) -> dict[str, Any]:
        """Check runtime health."""
        state = self.get_state()
        return {
            "status": state.status.value,
            "evaluations_active": state.evaluations_active,
            "evaluations_completed": state.evaluations_completed,
            "evaluations_failed": state.evaluations_failed,
            "snapshots_taken": state.snapshots_taken,
            "uptime_seconds": state.uptime_seconds,
            "recovery_attempts": state.recovery_attempts,
        }
