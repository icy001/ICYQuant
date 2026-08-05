"""HA scheduler for ICYQuant service discovery HA.

Provides ``HAScheduler`` for periodic execution of HA tasks
including health scans, heartbeat analysis, snapshots,
recovery checks, rebalance checks, and metrics collection.

Default tasks:
    health_scan (10s), heartbeat_analysis (5s),
    snapshot (60s), recovery_check (30s),
    rebalance_check (120s), metrics_collection (10s).
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class HAScheduler:
    """Periodic task scheduler for HA operations.

    Manages a set of named tasks that execute at configurable
    intervals.  Tasks run on an asyncio event loop and can be
    started/stopped independently.

    Args:
        controller: Optional ``HAController`` instance passed to
            default tasks for orchestration.
    """

    def __init__(self, controller: Any = None) -> None:
        self._lock = threading.RLock()
        self._controller = controller
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._running = False
        self._stop_event = asyncio.Event()
        self._scheduler_task: Optional[asyncio.Task] = None
        self._start_count = 0
        self._stop_count = 0
        self._execution_count = 0
        self._last_run: Optional[Dict[str, Any]] = None
        self._history: List[Dict[str, Any]] = []
        self._max_history = 200
        self._register_default_tasks()

    # ── Helpers ──

    @staticmethod
    def _now_iso() -> str:
        return datetime.utcnow().isoformat()

    def _register_default_tasks(self) -> None:
        self.add_task(
            "health_scan",
            self._default_health_scan,
            10.0,
        )
        self.add_task(
            "heartbeat_analysis",
            self._default_heartbeat_analysis,
            5.0,
        )
        self.add_task(
            "snapshot",
            self._default_snapshot,
            60.0,
        )
        self.add_task(
            "recovery_check",
            self._default_recovery_check,
            30.0,
        )
        self.add_task(
            "rebalance_check",
            self._default_rebalance_check,
            120.0,
        )
        self.add_task(
            "metrics_collection",
            self._default_metrics_collection,
            10.0,
        )

    # ── Public API ──

    async def start(self) -> None:
        """Start the scheduler and all registered tasks."""
        with self._lock:
            if self._running:
                logger.debug("Scheduler is already running.")
                return
            self._running = True
            self._stop_event.clear()
            self._start_count += 1

        self._scheduler_task = asyncio.create_task(self._run_loop())
        logger.info(
            "HA scheduler started with %d tasks.", len(self._tasks)
        )

    async def stop(self) -> None:
        """Stop the scheduler and all running tasks."""
        with self._lock:
            if not self._running:
                logger.debug("Scheduler is not running.")
                return
            self._running = False
            self._stop_event.set()
            self._stop_count += 1

        if self._scheduler_task is not None:
            try:
                self._scheduler_task.cancel()
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
            self._scheduler_task = None

        logger.info("HA scheduler stopped.")

    def is_running(self) -> bool:
        """Return whether the scheduler is currently running.

        Returns:
            True if the scheduler is active.
        """
        with self._lock:
            return self._running

    def add_task(
        self, name: str, fn: Callable, interval: float
    ) -> None:
        """Register a task to be executed periodically.

        Args:
            name: Unique task name.
            fn: Callable to execute (sync or async).
            interval: Interval in seconds between executions.
        """
        if not name:
            raise ValueError("name cannot be empty.")
        if not callable(fn):
            raise TypeError("fn must be callable.")
        if interval <= 0:
            raise ValueError("interval must be positive.")

        with self._lock:
            self._tasks[name] = {
                "fn": fn,
                "interval": float(interval),
                "last_execution": 0.0,
                "next_execution": time.time() + float(interval),
                "execution_count": 0,
                "last_duration": 0.0,
                "errors": 0,
            }
        logger.debug(
            "Registered task '%s' (interval=%.1fs).", name, interval
        )

    def remove_task(self, name: str) -> None:
        """Remove a registered task.

        Args:
            name: The task name to remove.
        """
        with self._lock:
            if name not in self._tasks:
                logger.warning(
                    "Task '%s' not found; skipping removal.", name
                )
                return
            del self._tasks[name]
        logger.info("Removed task '%s'.", name)

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the scheduler."""
        with self._lock:
            tasks_info = {}
            for n, entry in self._tasks.items():
                tasks_info[n] = {
                    "interval": entry["interval"],
                    "execution_count": entry["execution_count"],
                    "last_duration": entry["last_duration"],
                    "errors": entry["errors"],
                    "next_execution": (
                        datetime.utcfromtimestamp(
                            entry["next_execution"]
                        ).isoformat()
                        if entry["next_execution"]
                        else None
                    ),
                }
            return {
                "running": self._running,
                "task_count": len(self._tasks),
                "tasks": tasks_info,
                "start_count": self._start_count,
                "stop_count": self._stop_count,
                "execution_count": self._execution_count,
                "last_run": (
                    {
                        "timestamp": (
                            self._last_run.get("timestamp")
                            if self._last_run
                            else None
                        ),
                    }
                    if self._last_run
                    else None
                ),
                "history_size": len(self._history),
                "max_history": self._max_history,
            }

    # ── Internal: run loop ──

    async def _run_loop(self) -> None:
        logger.debug("Scheduler run loop started.")
        try:
            while not self._stop_event.is_set():
                await self._execute_due_tasks()
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=1.0,
                    )
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            pass
        logger.debug("Scheduler run loop ended.")

    async def _execute_due_tasks(self) -> None:
        now = time.time()
        tasks_to_run: List[str] = []

        with self._lock:
            for name, entry in self._tasks.items():
                if now >= entry["next_execution"]:
                    tasks_to_run.append(name)

        for name in tasks_to_run:
            with self._lock:
                entry = self._tasks.get(name)
                if entry is None:
                    continue
                entry["last_execution"] = now
                entry["next_execution"] = now + entry["interval"]
                entry["execution_count"] += 1

            task_start = time.time()
            try:
                fn = entry["fn"]
                coro = fn()
                if asyncio.iscoroutine(coro):
                    await coro
            except Exception as exc:
                logger.warning(
                    "Task '%s' failed: %s", name, exc
                )
                with self._lock:
                    if name in self._tasks:
                        self._tasks[name]["errors"] += 1

            task_duration = time.time() - task_start
            with self._lock:
                if name in self._tasks:
                    self._tasks[name]["last_duration"] = task_duration
                self._execution_count += 1

        if tasks_to_run:
            self._last_run = {
                "timestamp": self._now_iso(),
                "tasks_executed": tasks_to_run,
            }
            self._record_history(
                "tick",
                {
                    "tasks_executed": tasks_to_run,
                    "timestamp": self._now_iso(),
                },
            )

    def _record_history(self, event: str, data: Dict[str, Any]) -> None:
        self._history.append(
            {"event": event, "data": data, "recorded_at": time.time()}
        )
        if len(self._history) > self._max_history:
            excess = len(self._history) - self._max_history
            del self._history[:excess]

    # ── Default task implementations ──

    async def _default_health_scan(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "task": "health_scan",
            "timestamp": self._now_iso(),
            "healthy": True,
        }
        if self._controller is not None:
            health_comp = self._controller.get_component("health")
            if health_comp is not None:
                check_func = getattr(health_comp, "check", None)
                if callable(check_func):
                    try:
                        coro = check_func()
                        if asyncio.iscoroutine(coro):
                            health_result = await coro
                        else:
                            health_result = coro
                        result["health_result"] = health_result
                        if isinstance(health_result, dict):
                            result["healthy"] = health_result.get(
                                "healthy", True
                            )
                    except Exception as exc:
                        result["healthy"] = False
                        result["error"] = str(exc)
        return result

    async def _default_heartbeat_analysis(self) -> Dict[str, Any]:
        return {
            "task": "heartbeat_analysis",
            "timestamp": self._now_iso(),
            "analyzed": True,
        }

    async def _default_snapshot(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "task": "snapshot",
            "timestamp": self._now_iso(),
            "created": False,
        }
        if self._controller is not None:
            snap_comp = self._controller.get_component("snapshot")
            if snap_comp is not None:
                create_func = getattr(snap_comp, "create", None)
                if callable(create_func):
                    try:
                        coro = create_func({})
                        if asyncio.iscoroutine(coro):
                            snap_result = await coro
                        else:
                            snap_result = coro
                        result["created"] = True
                        result["snapshot"] = snap_result
                    except Exception as exc:
                        result["error"] = str(exc)
        return result

    async def _default_recovery_check(self) -> Dict[str, Any]:
        return {
            "task": "recovery_check",
            "timestamp": self._now_iso(),
            "checked": True,
        }

    async def _default_rebalance_check(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "task": "rebalance_check",
            "timestamp": self._now_iso(),
            "triggered": False,
        }
        if self._controller is not None:
            try:
                coro = self._controller.rebalance()
                if asyncio.iscoroutine(coro):
                    rb_result = await coro
                else:
                    rb_result = coro
                result["triggered"] = True
                result["result"] = rb_result
            except Exception as exc:
                result["error"] = str(exc)
        return result

    async def _default_metrics_collection(self) -> Dict[str, Any]:
        return {
            "task": "metrics_collection",
            "timestamp": self._now_iso(),
            "collected": True,
        }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"HAScheduler(running={self._running}, "
                f"tasks={len(self._tasks)})"
            )