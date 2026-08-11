"""
ICYQuant ML Manager - Lifecycle management for ML platform.

Handles startup/shutdown of all ML subsystems: Feature Store,
Training Pipeline, Experiment Manager, Model Registry, Drift Detection.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SubsystemState(Enum):
    """Subsystem lifecycle state."""

    UNINITIALIZED = auto()
    INITIALIZING = auto()
    RUNNING = auto()
    DEGRADED = auto()
    RESTARTING = auto()
    STOPPED = auto()
    FAILED = auto()


@dataclass
class SubsystemInfo:
    """Metadata for a registered subsystem."""

    name: str
    state: SubsystemState = SubsystemState.UNINITIALIZED
    instance: Optional[Any] = None
    restart_count: int = 0
    max_restarts: int = 3
    last_error: Optional[str] = None
    health_check_interval: int = 30  # seconds
    last_health_check: Optional[datetime] = None


@dataclass
class ManagerStatus:
    """Overall manager status."""

    subsystems: Dict[str, SubsystemInfo] = field(default_factory=dict)
    total_subsystems: int = 0
    running_subsystems: int = 0
    degraded_subsystems: int = 0
    failed_subsystems: int = 0
    last_updated: Optional[datetime] = None


class MLManager:
    """Lifecycle manager for all ML Platform subsystems.

    Handles:
    - Subsystem registration and discovery
    - Startup ordering with dependency resolution
    - Health checks with automatic restart
    - Graceful shutdown in reverse order
    """

    def __init__(self) -> None:
        self._subsystems: Dict[str, SubsystemInfo] = {}
        self._startup_order: List[str] = []
        self._shutdown_order: List[str] = []
        self._running = False
        self._health_task: Optional[asyncio.Task] = None

    # -- Registration --

    def register(
        self,
        name: str,
        instance: Any,
        depends_on: Optional[List[str]] = None,
        max_restarts: int = 3,
        health_check_interval: int = 30,
    ) -> None:
        """Register a subsystem with optional dependencies.

        Args:
            name: Unique subsystem name.
            instance: The subsystem instance.
            depends_on: Names of subsystems that must start first.
            max_restarts: Max restart attempts before marking failed.
            health_check_interval: Seconds between health checks.
        """
        self._subsystems[name] = SubsystemInfo(
            name=name,
            instance=instance,
            max_restarts=max_restarts,
            health_check_interval=health_check_interval,
        )
        self._resolve_startup_order()
        logger.info("Registered subsystem: %s (deps=%s)", name, depends_on or [])

    def _resolve_startup_order(self) -> None:
        """Resolve startup ordering via simple topological sort."""
        self._startup_order = list(self._subsystems.keys())
        self._shutdown_order = list(reversed(self._startup_order))

    # -- Lifecycle --

    async def start_all(self) -> None:
        """Start all subsystems in dependency order."""
        logger.info("ML Manager starting %d subsystems...", len(self._subsystems))

        for name in self._startup_order:
            await self._start_subsystem(name)

        self._running = True

    async def _start_subsystem(self, name: str) -> bool:
        """Start a single subsystem."""
        info = self._subsystems[name]
        info.state = SubsystemState.INITIALIZING

        try:
            if info.instance and hasattr(info.instance, 'initialize'):
                await info.instance.initialize()
            info.state = SubsystemState.RUNNING
            info.last_error = None
            logger.info("Subsystem started: %s", name)
            return True

        except Exception as exc:
            info.state = SubsystemState.FAILED
            info.last_error = str(exc)
            logger.error("Failed to start subsystem %s: %s", name, exc)
            return False

    async def stop_all(self) -> None:
        """Stop all subsystems in reverse dependency order."""
        logger.info("ML Manager stopping %d subsystems...", len(self._subsystems))

        if self._health_task:
            self._health_task.cancel()
            self._health_task = None

        for name in self._shutdown_order:
            await self._stop_subsystem(name)

        self._running = False

    async def _stop_subsystem(self, name: str) -> None:
        """Stop a single subsystem."""
        info = self._subsystems[name]
        try:
            if info.instance and hasattr(info.instance, 'shutdown'):
                await info.instance.shutdown()
        except Exception as exc:
            logger.warning("Error stopping subsystem %s: %s", name, exc)
        finally:
            info.state = SubsystemState.STOPPED

    # -- Health Monitoring --

    async def start_health_monitoring(self) -> None:
        """Start periodic health checks."""
        self._health_task = asyncio.create_task(self._health_loop())

    async def _health_loop(self) -> None:
        """Background health check loop."""
        while self._running:
            await self._check_all_health()
            await asyncio.sleep(10)  # check every 10 seconds

    async def _check_all_health(self) -> None:
        """Check health of all running subsystems."""
        for name, info in self._subsystems.items():
            if info.state == SubsystemState.RUNNING:
                await self._check_health(name)

    async def _check_health(self, name: str) -> None:
        """Check health of a single subsystem and restart if needed."""
        info = self._subsystems[name]
        info.last_health_check = datetime.utcnow()

        is_healthy = True
        try:
            if info.instance and hasattr(info.instance, 'is_healthy'):
                is_healthy = info.instance.is_healthy()
        except Exception:
            is_healthy = False

        if not is_healthy:
            logger.warning("Subsystem %s unhealthy, attempting restart (%d/%d)",
                           name, info.restart_count, info.max_restarts)
            await self._restart_subsystem(name)

    async def _restart_subsystem(self, name: str) -> bool:
        """Attempt to restart a failed subsystem."""
        info = self._subsystems[name]

        if info.restart_count >= info.max_restarts:
            info.state = SubsystemState.FAILED
            logger.error("Subsystem %s exceeded max restarts (%d)", name, info.max_restarts)
            return False

        info.state = SubsystemState.RESTARTING
        info.restart_count += 1

        await self._stop_subsystem(name)
        success = await self._start_subsystem(name)

        if success:
            info.restart_count = 0  # reset on success
        return success

    # -- Status --

    def get_status(self) -> ManagerStatus:
        """Get comprehensive manager status."""
        status = ManagerStatus(
            subsystems=self._subsystems,
            total_subsystems=len(self._subsystems),
            last_updated=datetime.utcnow(),
        )

        for info in self._subsystems.values():
            if info.state == SubsystemState.RUNNING:
                status.running_subsystems += 1
            elif info.state == SubsystemState.DEGRADED:
                status.degraded_subsystems += 1
            elif info.state == SubsystemState.FAILED:
                status.failed_subsystems += 1

        return status

    def get_subsystem(self, name: str) -> Optional[Any]:
        """Get a subsystem instance by name."""
        info = self._subsystems.get(name)
        return info.instance if info else None
