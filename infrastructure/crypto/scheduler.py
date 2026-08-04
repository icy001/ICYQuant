"""
Crypto scheduler for periodic operations.

Provides async task scheduling for recurring
crypto operations including key rotation,
health checks, and metrics collection.

Features:
- Key rotation scheduling (periodic checks for expiring keys)
- Health check scheduling (periodic health verification)
- Metrics collection scheduling
- Graceful shutdown support
- Task registration and cancellation
- Thread-safe with asyncio
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .service import CryptoService
from .manager import CryptoManager
from .health import CryptoHealthCheck
from .metrics import CryptoMetrics
from .keystore import KeyStore
from .keyring import Keyring

logger = logging.getLogger(__name__)


class CryptoScheduler:
    """
    Crypto periodic task scheduler.

    Manages async background tasks for recurring
    cryptographic operations including key rotation,
    health verification, and metrics collection.

    Usage:
        scheduler = CryptoScheduler(
            service=service,
            manager=manager,
        )
        await scheduler.start()
        # ... tasks run in background ...
        await scheduler.stop()
    """

    def __init__(
        self,
        service: Optional[CryptoService] = None,
        manager: Optional[CryptoManager] = None,
        health_check: Optional[CryptoHealthCheck] = None,
        metrics: Optional[CryptoMetrics] = None,
        key_store: Optional[KeyStore] = None,
        keyring: Optional[Keyring] = None,
        key_rotation_interval: int = 3600,
        health_check_interval: int = 60,
        metrics_interval: int = 30,
    ) -> None:
        """
        Initialize crypto scheduler.

        Args:
            service: CryptoService instance.
            manager: CryptoManager instance.
            health_check: CryptoHealthCheck instance.
            metrics: CryptoMetrics instance.
            key_store: KeyStore instance.
            keyring: Keyring instance.
            key_rotation_interval: Key rotation check interval
                in seconds (default: 3600 = 1 hour).
            health_check_interval: Health check interval
                in seconds (default: 60).
            metrics_interval: Metrics collection interval
                in seconds (default: 30).
        """
        self._service = service
        self._manager = manager
        self._health_check = health_check
        self._metrics = metrics
        self._key_store = key_store
        self._keyring = keyring

        self._key_rotation_interval = key_rotation_interval
        self._health_check_interval = health_check_interval
        self._metrics_interval = metrics_interval

        # Asyncio management
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._tasks: Dict[str, asyncio.Task] = {}
        self._running: bool = False
        self._lock = asyncio.Lock()

        # Scheduling state
        self._cycle_count: int = 0
        self._error_count: int = 0
        self._last_cycle_time: Optional[float] = None
        self._last_health_check: Optional[float] = None
        self._last_key_rotation: Optional[float] = None
        self._last_metrics_collection: Optional[float] = None

        # Registered custom tasks
        self._custom_tasks: Dict[str, Dict[str, Any]] = {}

    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running

    @property
    def cycle_count(self) -> int:
        """Get total cycle count."""
        return self._cycle_count

    @property
    def error_count(self) -> int:
        """Get total error count."""
        return self._error_count

    @property
    def key_rotation_interval(self) -> int:
        """Get key rotation interval."""
        return self._key_rotation_interval

    @property
    def health_check_interval(self) -> int:
        """Get health check interval."""
        return self._health_check_interval

    @property
    def metrics_interval(self) -> int:
        """Get metrics collection interval."""
        return self._metrics_interval

    async def start(self) -> None:
        """
        Start the scheduler.

        Launches all background tasks for periodic
        crypto operations. Idempotent - safe to call
        multiple times.
        """
        async with self._lock:
            if self._running:
                return

            self._loop = asyncio.get_running_loop()
            self._running = True

            # Start built-in tasks
            self._start_task(
                "key_rotation",
                self._run_key_rotation_loop,
            )
            self._start_task(
                "health_check",
                self._run_health_check_loop,
            )
            self._start_task(
                "metrics_collection",
                self._run_metrics_loop,
            )

            # Start custom tasks
            for task_name, task_info in self._custom_tasks.items():
                self._start_task(
                    task_name,
                    task_info["callback"],
                    task_info.get("interval"),
                )

            logger.info(
                "CryptoScheduler started with %d tasks",
                len(self._tasks),
            )

    async def stop(self) -> None:
        """
        Stop the scheduler gracefully.

        Cancels all background tasks and waits
        for them to complete. Idempotent - safe
        to call multiple times.
        """
        async with self._lock:
            if not self._running:
                return

            self._running = False

        # Cancel all tasks outside the lock to avoid deadlock
        task_names = list(self._tasks.keys())
        for name in task_names:
            task = self._tasks.pop(name, None)
            if task is not None and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.warning(
                        "Task %s raised during cancellation: %s",
                        name, e,
                    )

        logger.info("CryptoScheduler stopped")

    def register_task(
        self,
        name: str,
        callback: Callable,
        interval: Optional[int] = None,
    ) -> None:
        """
        Register a custom periodic task.

        Args:
            name: Unique task name.
            callback: Async callable to execute periodically.
            interval: Task interval in seconds.
                If None, runs once immediately.

        Raises:
            ValueError: If task name already registered.
        """
        if name in self._custom_tasks:
            raise ValueError(
                f"Task '{name}' is already registered"
            )

        self._custom_tasks[name] = {
            "callback": callback,
            "interval": interval,
        }

        # Start immediately if scheduler is running
        if self._running and self._loop is not None:
            self._start_task(name, callback, interval)

    def cancel_task(self, name: str) -> bool:
        """
        Cancel a registered task by name.

        Args:
            name: Task name to cancel.

        Returns:
            True if task was found and cancelled.
        """
        # Remove from custom tasks
        self._custom_tasks.pop(name, None)

        # Cancel running task
        task = self._tasks.pop(name, None)
        if task is not None and not task.done():
            task.cancel()
            return True
        return task is not None

    def list_tasks(self) -> List[Dict[str, Any]]:
        """List all registered tasks and their status."""
        result: List[Dict[str, Any]] = []

        for name, task in self._tasks.items():
            result.append({
                "name": name,
                "done": task.done(),
                "cancelled": task.cancelled(),
                "running": not task.done(),
            })

        return result

    async def run_once(self, task_name: str) -> Any:
        """
        Execute a single cycle of a named task.

        Args:
            task_name: Name of the task to run.

        Returns:
            Task execution result.

        Raises:
            ValueError: If task name not found.
        """
        task_info = self._custom_tasks.get(task_name)
        if task_info is None:
            raise ValueError(f"Task '{task_name}' not found")

        callback = task_info["callback"]
        if asyncio.iscoroutinefunction(callback):
            return await callback()
        return callback()

    async def _run_key_rotation_loop(self) -> None:
        """Periodic key rotation check loop."""
        while self._running:
            try:
                await self._check_key_rotation()
                self._cycle_count += 1
                self._last_key_rotation = time.time()
            except Exception as e:
                self._error_count += 1
                logger.error(
                    "Key rotation check failed: %s", e,
                )

            await asyncio.sleep(self._key_rotation_interval)

    async def _run_health_check_loop(self) -> None:
        """Periodic health check loop."""
        while self._running:
            try:
                await self._perform_health_check()
                self._last_health_check = time.time()
            except Exception as e:
                self._error_count += 1
                logger.error(
                    "Health check failed: %s", e,
                )

            await asyncio.sleep(self._health_check_interval)

    async def _run_metrics_loop(self) -> None:
        """Periodic metrics collection loop."""
        while self._running:
            try:
                await self._collect_metrics()
                self._last_metrics_collection = time.time()
            except Exception as e:
                self._error_count += 1
                logger.error(
                    "Metrics collection failed: %s", e,
                )

            await asyncio.sleep(self._metrics_interval)

    def _start_task(
        self,
        name: str,
        callback: Callable,
        interval: Optional[int] = None,
    ) -> None:
        """Start a background asyncio task."""
        if self._loop is None:
            return

        if interval is not None:
            task = self._loop.create_task(
                self._run_with_interval(name, callback, interval),
            )
        else:
            task = self._loop.create_task(callback())

        self._tasks[name] = task

    async def _run_with_interval(
        self,
        name: str,
        callback: Callable,
        interval: int,
    ) -> None:
        """Run a callback at a fixed interval."""
        while self._running:
            try:
                result = callback()
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                self._error_count += 1
                logger.error(
                    "Task '%s' failed: %s", name, e,
                )

            await asyncio.sleep(interval)

    async def _check_key_rotation(self) -> None:
        """Check for keys approaching expiration and rotate if needed."""
        if self._key_store is None or self._manager is None:
            return

        try:
            keys = self._key_store.list_keys()
            now = datetime.utcnow()
            expiring_keys: List[str] = []

            for key in keys:
                updated_at = key.updated_at
                if updated_at is None:
                    continue

                from datetime import timedelta
                ttl = timedelta(
                    seconds=self._key_rotation_interval,
                )
                if now - updated_at > ttl:
                    expiring_keys.append(key.key_id)

            if expiring_keys:
                logger.info(
                    "Found %d expiring keys, initiating rotation",
                    len(expiring_keys),
                )
                for key_id in expiring_keys:
                    try:
                        if self._service is not None:
                            await self._service.rotate_key(key_id)
                        logger.info(
                            "Rotated key: %s", key_id,
                        )
                    except Exception as e:
                        logger.error(
                            "Failed to rotate key %s: %s",
                            key_id, e,
                        )
        except Exception as e:
            logger.error(
                "Key rotation check failed: %s", e,
            )

    async def _perform_health_check(self) -> None:
        """Perform periodic health verification."""
        if self._health_check is None:
            return

        try:
            result = await self._health_check.check_all()
            if not result.get("healthy", False):
                logger.warning(
                    "Crypto health check reported unhealthy: %s",
                    result.get("components", {}),
                )
        except Exception as e:
            logger.error(
                "Health check loop failed: %s", e,
            )

    async def _collect_metrics(self) -> None:
        """Collect and record periodic metrics."""
        if self._metrics is None:
            return

        try:
            if self._service is not None:
                stats = self._service.get_stats()
                active_keys = 0

                if self._key_store is not None:
                    key_stats = self._key_store.get_stats()
                    active_keys = key_stats.get("total_keys", 0)

                self._metrics.set_active_keys(active_keys)
                self._metrics.set_active_operations(0)

        except Exception as e:
            logger.error(
                "Metrics collection failed: %s", e,
            )

    def get_status(self) -> Dict[str, Any]:
        """
        Get scheduler status.

        Returns:
            Status dictionary with scheduler state,
            task counts, and timing information.
        """
        return {
            "running": self._running,
            "cycle_count": self._cycle_count,
            "error_count": self._error_count,
            "last_cycle_time": (
                datetime.utcfromtimestamp(self._last_cycle_time).isoformat() + "Z"
                if self._last_cycle_time
                else None
            ),
            "last_health_check": (
                datetime.utcfromtimestamp(
                    self._last_health_check,
                ).isoformat() + "Z"
                if self._last_health_check
                else None
            ),
            "last_key_rotation": (
                datetime.utcfromtimestamp(
                    self._last_key_rotation,
                ).isoformat() + "Z"
                if self._last_key_rotation
                else None
            ),
            "last_metrics_collection": (
                datetime.utcfromtimestamp(
                    self._last_metrics_collection,
                ).isoformat() + "Z"
                if self._last_metrics_collection
                else None
            ),
            "registered_tasks": len(self._tasks),
            "custom_tasks": list(self._custom_tasks.keys()),
            "intervals": {
                "key_rotation": self._key_rotation_interval,
                "health_check": self._health_check_interval,
                "metrics": self._metrics_interval,
            },
        }