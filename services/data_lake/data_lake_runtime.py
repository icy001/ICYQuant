"""
Data Lake Runtime — background task management, worker pools,
and event loop coordination for the data lake.

Commit 16 Part 1.3
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class DataLakeRuntimeStatus(str, Enum):
    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class DataLakeRuntimeConfig:
    runtime_id: str = "icyquant-datalake-runtime"
    worker_count: int = 4
    task_queue_size: int = 10_000
    monitor_interval: float = 5.0
    heartbeat_interval: float = 30.0


@dataclass
class WorkerStats:
    worker_id: int
    tasks_processed: int = 0
    tasks_failed: int = 0
    avg_latency_ms: float = 0.0
    last_active: str = ""


class DataLakeRuntime:
    """
    Background runtime for Data Lake operations.

    Manages worker pools, scheduled tasks, health monitoring,
    and graceful shutdown coordination.
    """

    def __init__(self, config: Optional[DataLakeRuntimeConfig] = None) -> None:
        self.config = config or DataLakeRuntimeConfig()
        self._status = DataLakeRuntimeStatus.CREATED
        self._workers: list[asyncio.Task] = []
        self._task_queue: asyncio.Queue = asyncio.Queue(maxsize=self.config.task_queue_size)
        self._worker_stats: dict[int, WorkerStats] = {}
        self._monitor_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        self._paused_event = asyncio.Event()

    async def initialize(self) -> None:
        self._status = DataLakeRuntimeStatus.INITIALIZING
        for i in range(self.config.worker_count):
            self._worker_stats[i] = WorkerStats(worker_id=i)
        self._status = DataLakeRuntimeStatus.STOPPED
        logger.info("Data Lake Runtime initialized: %d workers", self.config.worker_count)

    async def start(self) -> None:
        self._status = DataLakeRuntimeStatus.RUNNING
        self._shutdown_event.clear()
        self._paused_event.clear()

        for i in range(self.config.worker_count):
            task = asyncio.create_task(self._worker_loop(i), name=f"dl-worker-{i}")
            self._workers.append(task)

        self._monitor_task = asyncio.create_task(self._monitor_loop(), name="dl-monitor")
        logger.info("Data Lake Runtime started with %d workers", len(self._workers))

    async def stop(self) -> None:
        self._status = DataLakeRuntimeStatus.STOPPING
        self._shutdown_event.set()
        self._paused_event.set()

        # Drain queue
        remaining = []
        while not self._task_queue.empty():
            try:
                remaining.append(self._task_queue.get_nowait())
            except asyncio.QueueEmpty:
                break

        if self._monitor_task:
            self._monitor_task.cancel()
        for task in self._workers:
            task.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)

        self._workers.clear()
        self._status = DataLakeRuntimeStatus.STOPPED
        logger.info("Data Lake Runtime stopped (%d pending tasks dropped)", len(remaining))

    async def pause(self) -> None:
        self._status = DataLakeRuntimeStatus.PAUSED
        self._paused_event.set()

    async def resume(self) -> None:
        self._paused_event.clear()
        self._status = DataLakeRuntimeStatus.RUNNING

    async def submit(self, coro_func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """Submit a coroutine for background execution."""
        if self._status != DataLakeRuntimeStatus.RUNNING:
            raise RuntimeError(f"Runtime not running: {self._status}")
        await self._task_queue.put((coro_func, args, kwargs))

    async def _worker_loop(self, worker_id: int) -> None:
        stats = self._worker_stats[worker_id]
        while not self._shutdown_event.is_set():
            if self._paused_event.is_set():
                await asyncio.sleep(0.1)
                continue

            try:
                coro_func, args, kwargs = await asyncio.wait_for(
                    self._task_queue.get(), timeout=1.0
                )
                start = asyncio.get_event_loop().time()
                try:
                    await coro_func(*args, **kwargs)
                    stats.tasks_processed += 1
                except Exception:
                    stats.tasks_failed += 1
                    logger.exception("Worker %d task failed", worker_id)
                elapsed = (asyncio.get_event_loop().time() - start) * 1000
                stats.avg_latency_ms = (stats.avg_latency_ms * 0.9 + elapsed * 0.1)
            except asyncio.TimeoutError:
                pass

    async def _monitor_loop(self) -> None:
        while not self._shutdown_event.is_set():
            await asyncio.sleep(self.config.monitor_interval)
            total_processed = sum(s.tasks_processed for s in self._worker_stats.values())
            total_failed = sum(s.tasks_failed for s in self._worker_stats.values())
            queue_size = self._task_queue.qsize()
            logger.debug(
                "Runtime stats: processed=%d failed=%d queue=%d",
                total_processed, total_failed, queue_size,
            )

    @property
    def status(self) -> DataLakeRuntimeStatus:
        return self._status

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "status": self._status.value,
            "workers": self.config.worker_count,
            "queue_size": self._task_queue.qsize(),
            "worker_stats": {
                wid: {
                    "processed": s.tasks_processed,
                    "failed": s.tasks_failed,
                    "avg_latency_ms": round(s.avg_latency_ms, 2),
                }
                for wid, s in self._worker_stats.items()
            },
        }
