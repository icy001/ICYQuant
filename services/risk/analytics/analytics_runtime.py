"""
Analytics Runtime — Runtime environment for the enterprise risk analytics pipeline.

Manages the execution lifecycle, concurrency control, state persistence,
and heartbeat for continuous risk analytics operations.
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
    """Analytics runtime status."""
    CREATED = "CREATED"
    INITIALIZING = "INITIALIZING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    RECOVERING = "RECOVERING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


@dataclass
class AnalyticsRuntimeConfig:
    """Configuration for analytics runtime."""
    max_concurrent_analyses: int = 20
    analysis_timeout_seconds: float = 300.0
    heartbeat_interval_seconds: float = 5.0
    snapshot_interval_seconds: float = 10.0
    enable_persistence: bool = True
    auto_recovery: bool = True
    max_recovery_attempts: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeState:
    """Current state of the analytics runtime."""
    status: RuntimeStatus = RuntimeStatus.CREATED
    analyses_active: int = 0
    analyses_completed: int = 0
    analyses_failed: int = 0
    stress_tests_run: int = 0
    var_calculations: int = 0
    scenarios_run: int = 0
    reports_generated: int = 0
    started_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    uptime_seconds: float = 0.0
    recovery_attempts: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class AnalyticsRuntime:
    """
    Runtime environment for the enterprise risk analytics pipeline.

    Manages execution lifecycle, concurrency, state persistence,
    and periodic heartbeats for continuous analytics operations.

    Usage::

        runtime = AnalyticsRuntime(config=AnalyticsRuntimeConfig())
        await runtime.initialize()
        await runtime.start()
        state = runtime.get_state()
    """

    def __init__(self, config: Optional[AnalyticsRuntimeConfig] = None) -> None:
        self._config = config or AnalyticsRuntimeConfig()
        self._state = RuntimeState()
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._snapshot_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    @property
    def status(self) -> RuntimeStatus:
        return self._state.status

    @property
    def config(self) -> AnalyticsRuntimeConfig:
        return self._config

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize the analytics runtime."""
        self._state.status = RuntimeStatus.INITIALIZING
        logger.info("AnalyticsRuntime initializing...")
        self._state.status = RuntimeStatus.CREATED
        logger.info("AnalyticsRuntime initialized.")

    async def start(self) -> None:
        """Start the analytics runtime and background tasks."""
        self._state.status = RuntimeStatus.RUNNING
        self._state.started_at = datetime.now(timezone.utc)
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        if self._config.enable_persistence:
            self._snapshot_task = asyncio.create_task(self._snapshot_loop())
        logger.info("AnalyticsRuntime started.")

    async def stop(self) -> None:
        """Stop the analytics runtime and cancel background tasks."""
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
        logger.info("AnalyticsRuntime stopped.")

    async def pause(self) -> None:
        """Pause analyses."""
        self._state.status = RuntimeStatus.PAUSED
        logger.info("AnalyticsRuntime paused.")

    async def resume(self) -> None:
        """Resume analyses."""
        self._state.status = RuntimeStatus.RUNNING
        logger.info("AnalyticsRuntime resumed.")

    async def recover(self) -> None:
        """Attempt runtime recovery."""
        if self._state.recovery_attempts >= self._config.max_recovery_attempts:
            self._state.status = RuntimeStatus.ERROR
            logger.error("AnalyticsRuntime: max recovery attempts exceeded.")
            return

        self._state.status = RuntimeStatus.RECOVERING
        self._state.recovery_attempts += 1
        self._state.analyses_failed = 0
        self._state.status = RuntimeStatus.RUNNING
        logger.info(f"AnalyticsRuntime recovered (attempt {self._state.recovery_attempts}).")

    # ---- State ----

    def get_state(self) -> RuntimeState:
        """Get current runtime state."""
        if self._state.started_at:
            self._state.uptime_seconds = (
                datetime.now(timezone.utc) - self._state.started_at
            ).total_seconds()
        return self._state

    async def record_analysis_start(self) -> None:
        """Record the start of an analysis."""
        async with self._lock:
            self._state.analyses_active += 1

    async def record_analysis_complete(self, success: bool = True) -> None:
        """Record the completion of an analysis."""
        async with self._lock:
            self._state.analyses_active = max(0, self._state.analyses_active - 1)
            if success:
                self._state.analyses_completed += 1
            else:
                self._state.analyses_failed += 1

    async def record_stress_test(self) -> None:
        """Record a stress test execution."""
        async with self._lock:
            self._state.stress_tests_run += 1

    async def record_var_calculation(self) -> None:
        """Record a VaR calculation."""
        async with self._lock:
            self._state.var_calculations += 1

    async def record_scenario_run(self) -> None:
        """Record a scenario run."""
        async with self._lock:
            self._state.scenarios_run += 1

    async def record_report_generated(self) -> None:
        """Record a report generation."""
        async with self._lock:
            self._state.reports_generated += 1

    # ---- Persistence ----

    async def save_snapshot(self) -> dict[str, Any]:
        """Save current runtime state as a snapshot."""
        state = self.get_state()
        return {
            "status": state.status.value,
            "analyses_active": state.analyses_active,
            "analyses_completed": state.analyses_completed,
            "analyses_failed": state.analyses_failed,
            "stress_tests_run": state.stress_tests_run,
            "var_calculations": state.var_calculations,
            "scenarios_run": state.scenarios_run,
            "reports_generated": state.reports_generated,
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
        self._state.analyses_completed = snapshot.get("analyses_completed", 0)
        self._state.analyses_failed = snapshot.get("analyses_failed", 0)
        self._state.stress_tests_run = snapshot.get("stress_tests_run", 0)
        self._state.var_calculations = snapshot.get("var_calculations", 0)
        self._state.scenarios_run = snapshot.get("scenarios_run", 0)
        self._state.reports_generated = snapshot.get("reports_generated", 0)
        logger.info("AnalyticsRuntime restored from snapshot.")

    # ---- Health ----

    async def health_check(self) -> dict[str, Any]:
        """Check runtime health."""
        state = self.get_state()
        return {
            "status": state.status.value,
            "analyses_active": state.analyses_active,
            "analyses_completed": state.analyses_completed,
            "analyses_failed": state.analyses_failed,
            "stress_tests_run": state.stress_tests_run,
            "var_calculations": state.var_calculations,
            "scenarios_run": state.scenarios_run,
            "reports_generated": state.reports_generated,
            "uptime_seconds": state.uptime_seconds,
            "recovery_attempts": state.recovery_attempts,
        }

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
