"""Autonomy Runtime — Execution environment for autonomous research.

Manages the concurrent execution of research tasks, experiment runs,
and factor mining operations within compute budget constraints.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class ResearchTask:
    """A single autonomous research task."""

    task_id: str
    task_type: str  # scan, hypothesis, factor_mine, alpha_discover, backtest
    status: str = "queued"
    priority: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class AutonomyRuntime:
    """Autonomy Runtime — manages research task concurrency.

    Provides controlled execution of autonomous research tasks with:
        - Task prioritization
        - Concurrency limiting
        - Timeout enforcement
        - Resource tracking
    """

    def __init__(self, max_concurrency: int = 10) -> None:
        self.max_concurrency = max_concurrency
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._active_tasks: Dict[str, ResearchTask] = {}
        self._completed_tasks: Set[str] = set()
        self._running = False

        self._stats = {
            "total_tasks": 0,
            "completed": 0,
            "failed": 0,
            "timed_out": 0,
        }

    async def start(self) -> None:
        self._running = True
        self._semaphore = asyncio.Semaphore(self.max_concurrency)
        logger.info("Autonomy Runtime started (max_concurrency=%d)", self.max_concurrency)

    async def stop(self) -> None:
        logger.info("Autonomy Runtime stopping")
        self._running = False

        # Cancel active tasks
        for task_id in list(self._active_tasks.keys()):
            t = self._active_tasks.pop(task_id, None)
            if t:
                t.status = "cancelled"

        logger.info("Autonomy Runtime stopped")

    async def execute(
        self,
        task_type: str,
        coro,
        priority: int = 0,
        timeout: float = 300.0,
        **metadata,
    ) -> Any:
        """Execute a research task with concurrency control.

        Args:
            task_type: Type of research task.
            coro: Awaitable to execute.
            priority: Higher = sooner.
            timeout: Max execution time in seconds.
            **metadata: Additional task metadata.

        Returns:
            Result of the coroutine.
        """
        if not self._running:
            raise RuntimeError("Runtime not running")

        task = ResearchTask(
            task_id=f"rt_{task_type}_{time.monotonic_ns()}",
            task_type=task_type,
            priority=priority,
            metadata=metadata,
        )

        self._stats["total_tasks"] += 1
        self._active_tasks[task.task_id] = task

        try:
            async with self._semaphore:
                task.status = "running"
                task.started_at = datetime.now(timezone.utc)

                try:
                    result = await asyncio.wait_for(coro, timeout=timeout)
                    task.status = "completed"
                    task.result = result
                    self._stats["completed"] += 1
                    return result

                except asyncio.TimeoutError:
                    task.status = "timed_out"
                    task.error = f"Timeout after {timeout}s"
                    self._stats["timed_out"] += 1
                    raise TimeoutError(f"Task {task_type} timed out")

        except Exception as exc:
            task.status = "failed"
            task.error = str(exc)
            self._stats["failed"] += 1
            raise

        finally:
            task.completed_at = datetime.now(timezone.utc)
            self._active_tasks.pop(task.task_id, None)
            self._completed_tasks.add(task.task_id)

    async def health(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "active_tasks": len(self._active_tasks),
            "max_concurrency": self.max_concurrency,
            "stats": dict(self._stats),
        }
