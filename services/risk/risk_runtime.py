"""
Risk Runtime — Runtime environment for the Risk Management Platform.

Manages risk evaluation execution context, state persistence,
resource allocation, and runtime lifecycle.
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
    """Risk runtime status."""
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
    """Runtime configuration."""
    max_concurrent_evaluations: int = 50
    evaluation_timeout_seconds: float = 10.0
    heartbeat_interval_seconds: float = 5.0
    enable_persistence: bool = True
    snapshot_interval_minutes: int = 15
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeState:
    """Current runtime state snapshot."""
    status: RuntimeStatus = RuntimeStatus.CREATED
    evaluations_active: int = 0
    evaluations_completed: int = 0
    evaluations_failed: int = 0
    started_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    uptime_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class RiskRuntime:
    """
    Runtime environment for the Risk Management Platform.

    Manages the execution lifecycle, resource allocation, and state
    persistence for all risk evaluation operations.

    Usage::

        runtime = RiskRuntime(config=RuntimeConfig())
        await runtime.initialize()
        await runtime.start()
        state = runtime.get_state()
    """

    def __init__(self, config: Optional[RuntimeConfig] = None) -> None:
        self._config = config or RuntimeConfig()
        self._state = RuntimeState()
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    @property
    def status(self) -> RuntimeStatus:
        return self._state.status

    @property
    def config(self) -> RuntimeConfig:
        return self._config

    async def initialize(self) -> None:
        """Initialize the risk runtime."""
        self._state.status = RuntimeStatus.INITIALIZING
        logger.info("RiskRuntime initializing...")
        self._state.status = RuntimeStatus.CREATED
        logger.info("RiskRuntime initialized.")

    async def start(self) -> None:
        """Start the risk runtime."""
        self._state.status = RuntimeStatus.RUNNING
        self._state.started_at = datetime.now(timezone.utc)
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("RiskRuntime started.")

    async def stop(self) -> None:
        """Stop the risk runtime."""
        self._state.status = RuntimeStatus.STOPPING
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        self._state.status = RuntimeStatus.STOPPED
        logger.info("RiskRuntime stopped.")

    async def pause(self) -> None:
        """Pause the runtime evaluations."""
        self._state.status = RuntimeStatus.PAUSED
        logger.info("RiskRuntime paused.")

    async def resume(self) -> None:
        """Resume the runtime evaluations."""
        self._state.status = RuntimeStatus.RUNNING
        logger.info("RiskRuntime resumed.")

    async def recover(self) -> None:
        """Recover runtime from error state."""
        self._state.status = RuntimeStatus.RECOVERING
        self._state.evaluations_failed = 0
        self._state.status = RuntimeStatus.RUNNING
        logger.info("RiskRuntime recovered.")

    # ---- State Management ----

    def get_state(self) -> RuntimeState:
        """Get current runtime state."""
        if self._state.started_at:
            self._state.uptime_seconds = (datetime.now(timezone.utc) - self._state.started_at).total_seconds()
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

    # ---- Persistence ----

    async def save_snapshot(self) -> dict[str, Any]:
        """Save current runtime state as a snapshot."""
        state = self.get_state()
        snapshot = {
            "status": state.status.value,
            "evaluations_active": state.evaluations_active,
            "evaluations_completed": state.evaluations_completed,
            "evaluations_failed": state.evaluations_failed,
            "uptime_seconds": state.uptime_seconds,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logger.debug("Runtime snapshot saved.")
        return snapshot

    async def restore_snapshot(self, snapshot: dict[str, Any]) -> None:
        """Restore runtime state from a snapshot."""
        self._state.status = RuntimeStatus(snapshot.get("status", "created"))
        self._state.evaluations_completed = snapshot.get("evaluations_completed", 0)
        self._state.evaluations_failed = snapshot.get("evaluations_failed", 0)
        logger.info("Runtime restored from snapshot.")

    # ---- Internal ----

    async def _heartbeat_loop(self) -> None:
        """Periodic heartbeat."""
        while True:
            try:
                await asyncio.sleep(self._config.heartbeat_interval_seconds)
                self._state.last_heartbeat = datetime.now(timezone.utc)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

    async def health_check(self) -> dict[str, Any]:
        """Check runtime health."""
        state = self.get_state()
        return {
            "status": state.status.value,
            "evaluations_active": state.evaluations_active,
            "evaluations_completed": state.evaluations_completed,
            "evaluations_failed": state.evaluations_failed,
            "uptime_seconds": state.uptime_seconds,
        }
