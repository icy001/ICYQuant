"""
Connectivity Runtime — Manages the runtime state and lifecycle
of the Market Connectivity Platform with health monitoring,
reconnect orchestration, and metrics collection.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class ConnectivityRuntimeStatus(str, Enum):
    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class ConnectivityRuntimeConfig:
    platform_id: str = "icyquant-market-connectivity"
    auto_reconnect: bool = True
    health_check_interval: float = 5.0
    max_concurrent_connections: int = 256
    reconnect_max_retries: int = 10
    reconnect_base_delay: float = 1.0
    reconnect_max_delay: float = 60.0


@dataclass
class RuntimeState:
    status: ConnectivityRuntimeStatus = ConnectivityRuntimeStatus.CREATED
    active_connections: int = 0
    total_connections_established: int = 0
    total_connection_failures: int = 0
    total_reconnects: int = 0
    uptime_seconds: float = 0.0
    last_health_check: float = 0.0
    errors: list[str] = field(default_factory=list)


class ConnectivityRuntime:
    """
    Runtime engine for the Market Connectivity Platform.

    Manages the background event loop, health check scheduling,
    and automatic reconnect coordination for all exchange connections.

    Usage::

        runtime = ConnectivityRuntime(config)
        await runtime.initialize()
        await runtime.start()
        status = await runtime.get_status()
        await runtime.stop()
    """

    def __init__(self, config: Optional[ConnectivityRuntimeConfig] = None) -> None:
        self.config = config or ConnectivityRuntimeConfig()
        self._state = RuntimeState()
        self._tasks: list[asyncio.Task] = []
        self._health_check_callback: Optional[Callable] = None
        self._reconnect_callback: Optional[Callable] = None
        self._started_at: float = 0.0
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the runtime."""
        self._state.status = ConnectivityRuntimeStatus.INITIALIZING
        logger.info("ConnectivityRuntime initializing...")
        self._state.status = ConnectivityRuntimeStatus.CREATED
        logger.info("ConnectivityRuntime initialized.")

    async def start(self) -> None:
        """Start the runtime event loop and background tasks."""
        if self._state.status == ConnectivityRuntimeStatus.RUNNING:
            return

        self._state.status = ConnectivityRuntimeStatus.RUNNING
        self._started_at = time.monotonic()
        logger.info("ConnectivityRuntime started.")

        if self.config.health_check_interval > 0:
            task = asyncio.create_task(self._health_check_loop())
            self._tasks.append(task)

        if self.config.auto_reconnect:
            task = asyncio.create_task(self._reconnect_loop())
            self._tasks.append(task)

    async def stop(self) -> None:
        """Stop the runtime and cancel background tasks."""
        if self._state.status == ConnectivityRuntimeStatus.STOPPED:
            return

        self._state.status = ConnectivityRuntimeStatus.STOPPING
        logger.info("ConnectivityRuntime stopping...")

        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        self._state.status = ConnectivityRuntimeStatus.STOPPED
        logger.info("ConnectivityRuntime stopped.")

    def register_health_check_callback(self, callback: Callable) -> None:
        """Register a callback for health check execution."""
        self._health_check_callback = callback

    def register_reconnect_callback(self, callback: Callable) -> None:
        """Register a callback for reconnect execution."""
        self._reconnect_callback = callback

    async def get_status(self) -> dict[str, Any]:
        """Get current runtime status."""
        if self._state.status == ConnectivityRuntimeStatus.RUNNING:
            self._state.uptime_seconds = time.monotonic() - self._started_at

        return {
            "status": self._state.status.value,
            "active_connections": self._state.active_connections,
            "total_connections_established": self._state.total_connections_established,
            "total_connection_failures": self._state.total_connection_failures,
            "total_reconnects": self._state.total_reconnects,
            "uptime_seconds": self._state.uptime_seconds,
            "last_health_check": self._state.last_health_check,
        }

    async def record_connection_established(self) -> None:
        """Record a successful connection establishment."""
        async with self._lock:
            self._state.active_connections += 1
            self._state.total_connections_established += 1

    async def record_connection_closed(self) -> None:
        """Record a connection closure."""
        async with self._lock:
            self._state.active_connections = max(0, self._state.active_connections - 1)

    async def record_connection_failure(self, error: str = "") -> None:
        """Record a connection failure."""
        async with self._lock:
            self._state.total_connection_failures += 1
            self._state.active_connections = max(0, self._state.active_connections - 1)
            if error:
                self._state.errors.append(error)
                if len(self._state.errors) > 100:
                    self._state.errors = self._state.errors[-100:]

    async def record_reconnect(self) -> None:
        """Record a reconnection event."""
        async with self._lock:
            self._state.total_reconnects += 1

    async def _health_check_loop(self) -> None:
        """Background health check loop."""
        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                self._state.last_health_check = time.monotonic()
                if self._health_check_callback:
                    await self._health_check_callback()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Health check loop error")

    async def _reconnect_loop(self) -> None:
        """Background reconnect orchestration loop."""
        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval * 2)
                if self._reconnect_callback:
                    await self._reconnect_callback()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Reconnect loop error")
