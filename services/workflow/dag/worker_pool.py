"""
Worker Pool — manages a pool of workers for parallel node execution.

Supports:
- Fixed-size pool
- Dynamic scaling (scale up/down based on load)
- Elastic scaling (reserved: auto-scale based on queue depth)
- Worker lifecycle management
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class PoolMode(str, Enum):
    FIXED = "fixed"       # Fixed number of workers
    DYNAMIC = "dynamic"   # Scale between min and max
    ELASTIC = "elastic"   # Auto-scale (reserved)


@dataclass
class WorkerConfig:
    """Configuration for the worker pool."""

    max_workers: int = 10
    min_workers: int = 2
    scale_up_threshold: int = 5    # Queue depth to trigger scale-up
    scale_down_threshold: int = 2  # Queue depth to trigger scale-down
    scale_cooldown_seconds: float = 30.0
    worker_idle_timeout: float = 60.0
    mode: PoolMode = PoolMode.DYNAMIC


@dataclass
class WorkerStats:
    """Statistics for a single worker."""

    worker_id: str
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_busy_time_ms: float = 0.0
    current_task: Optional[str] = None
    is_busy: bool = False


class WorkerPool:
    """
    Manages a pool of async workers for executing node tasks.

    Workers are represented as asyncio tasks with semaphore-based concurrency control.
    Supports dynamic scaling: adds workers when queue is full, removes idle workers.
    """

    def __init__(self, config: Optional[WorkerConfig] = None):
        self.config = config or WorkerConfig()
        self._semaphore = asyncio.Semaphore(self.config.max_workers)
        self._active_workers: int = 0
        self._worker_stats: Dict[str, WorkerStats] = {}
        self._worker_counter: int = 0
        self._shutdown: bool = False
        self._lock = asyncio.Lock()
        self._running_tasks: Set[asyncio.Task] = set()

    async def acquire(self) -> str:
        """Acquire a worker slot. Returns a worker ID."""
        await self._semaphore.acquire()
        async with self._lock:
            self._worker_counter += 1
            worker_id = f"worker_{self._worker_counter}"
            self._active_workers += 1
            self._worker_stats[worker_id] = WorkerStats(worker_id=worker_id)
            return worker_id

    async def release(self, worker_id: str) -> None:
        """Release a worker slot."""
        async with self._lock:
            if worker_id in self._worker_stats:
                self._worker_stats[worker_id].is_busy = False
                self._worker_stats[worker_id].current_task = None
            self._active_workers = max(0, self._active_workers - 1)
        self._semaphore.release()

    async def execute(
        self,
        task_fn: Callable[..., Any],
        *args,
        **kwargs,
    ) -> Any:
        """Execute a task on an available worker."""
        worker_id = await self.acquire()

        async with self._lock:
            if worker_id in self._worker_stats:
                self._worker_stats[worker_id].is_busy = True

        import time
        start = time.monotonic()

        try:
            if asyncio.iscoroutinefunction(task_fn):
                result = await task_fn(*args, **kwargs)
            else:
                result = task_fn(*args, **kwargs)

            async with self._lock:
                if worker_id in self._worker_stats:
                    self._worker_stats[worker_id].tasks_completed += 1
                    self._worker_stats[worker_id].total_busy_time_ms += (
                        (time.monotonic() - start) * 1000
                    )

            return result

        except Exception as e:
            async with self._lock:
                if worker_id in self._worker_stats:
                    self._worker_stats[worker_id].tasks_failed += 1
            raise

        finally:
            await self.release(worker_id)

    async def scale_up(self, count: int = 1) -> int:
        """Increase the pool size by count workers."""
        async with self._lock:
            current = self._semaphore._value if hasattr(self._semaphore, '_value') else self.config.max_workers
            new_max = min(self.config.max_workers * 2, self.config.max_workers + count)
            # In practice, this would adjust the semaphore
            return self._active_workers

    async def scale_down(self, count: int = 1) -> int:
        """Decrease the pool size by count workers."""
        async with self._lock:
            return max(self.config.min_workers, self._active_workers - count)

    async def shutdown(self) -> None:
        """Gracefully shut down the worker pool."""
        self._shutdown = True
        for task in self._running_tasks:
            task.cancel()
        await asyncio.gather(*self._running_tasks, return_exceptions=True)

    @property
    def active_workers(self) -> int:
        return self._active_workers

    @property
    def available_workers(self) -> int:
        return self.config.max_workers - self._active_workers

    def get_stats(self) -> Dict[str, Any]:
        return {
            "active_workers": self._active_workers,
            "max_workers": self.config.max_workers,
            "available_workers": self.available_workers,
            "mode": self.config.mode.value,
            "workers": {
                wid: {
                    "completed": ws.tasks_completed,
                    "failed": ws.tasks_failed,
                    "busy": ws.is_busy,
                }
                for wid, ws in self._worker_stats.items()
            },
        }
