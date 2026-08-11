"""
Evolution Runtime — Concurrent execution environment for evolution workloads.

Manages async task scheduling, compute resource allocation, and parallel
evaluation of factor/alpha candidates during evolution runs.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class EvolutionTask:
    """A unit of work in the evolution runtime."""

    task_id: str
    task_type: str  # "mutation", "crossover", "fitness", "validation", "backtest"
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    payload: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0
    retries: int = 0
    max_retries: int = 2


@dataclass
class ComputeResources:
    """Track compute resource usage."""

    max_concurrent_tasks: int = 16
    max_backtests_per_hour: int = 200
    max_gpu_hours: float = 8.0
    available_cpu_cores: int = 8
    available_memory_gb: float = 32.0

    active_tasks: int = 0
    backtests_run: int = 0
    gpu_hours_used: float = 0.0
    cpu_utilization: float = 0.0
    memory_used_gb: float = 0.0


class EvolutionRuntime:
    """
    Async execution environment for evolution operations.

    Features:
        - Priority-based task scheduling
        - Concurrency control with semaphores
        - Compute resource tracking
        - Backtest rate limiting
        - Task retry with backoff
        - Graceful shutdown
    """

    def __init__(
        self,
        resources: Optional[ComputeResources] = None,
        max_concurrency: int = 16,
    ):
        self._resources = resources or ComputeResources()
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._active_tasks: Dict[str, EvolutionTask] = {}
        self._completed_tasks: List[EvolutionTask] = []
        self._running = False
        self._backtest_semaphore = asyncio.Semaphore(
            self._resources.max_backtests_per_hour // 60
        )

    # ── Task Submission ────────────────────────────────────

    async def submit_mutation(
        self,
        individual_id: str,
        genome: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> EvolutionTask:
        """Submit a factor/alpha mutation task."""
        task = EvolutionTask(
            task_id=f"mut-{individual_id[:8]}",
            task_type="mutation",
            priority=priority,
            payload={"individual_id": individual_id, "genome": genome},
        )
        await self._enqueue(task)
        return task

    async def submit_crossover(
        self,
        parent_a_id: str,
        parent_b_id: str,
        genome_a: Dict[str, Any],
        genome_b: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> EvolutionTask:
        """Submit a factor/alpha crossover task."""
        task = EvolutionTask(
            task_id=f"xover-{parent_a_id[:4]}-{parent_b_id[:4]}",
            task_type="crossover",
            priority=priority,
            payload={
                "parent_a": parent_a_id,
                "parent_b": parent_b_id,
                "genome_a": genome_a,
                "genome_b": genome_b,
            },
        )
        await self._enqueue(task)
        return task

    async def submit_fitness_evaluation(
        self,
        individual_id: str,
        genome: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> EvolutionTask:
        """Submit a fitness evaluation task."""
        task = EvolutionTask(
            task_id=f"fit-{individual_id[:8]}",
            task_type="fitness",
            priority=priority,
            payload={"individual_id": individual_id, "genome": genome},
        )
        await self._enqueue(task)
        return task

    async def submit_validation(
        self,
        individual_id: str,
        genome: Dict[str, Any],
        validation_types: List[str],
        priority: TaskPriority = TaskPriority.HIGH,
    ) -> EvolutionTask:
        """Submit validation tasks (OOS, walk-forward, regime, etc.)."""
        task = EvolutionTask(
            task_id=f"val-{individual_id[:8]}",
            task_type="validation",
            priority=priority,
            payload={
                "individual_id": individual_id,
                "genome": genome,
                "validation_types": validation_types,
            },
        )
        await self._enqueue(task)
        return task

    async def submit_backtest(
        self,
        individual_id: str,
        strategy_spec: Dict[str, Any],
        priority: TaskPriority = TaskPriority.HIGH,
    ) -> EvolutionTask:
        """Submit a backtest task with rate limiting."""
        task = EvolutionTask(
            task_id=f"bt-{individual_id[:8]}",
            task_type="backtest",
            priority=priority,
            payload={"individual_id": individual_id, "strategy_spec": strategy_spec},
        )
        await self._enqueue(task)
        return task

    # ── Queue Management ───────────────────────────────────

    async def _enqueue(self, task: EvolutionTask) -> None:
        """Enqueue a task with priority ordering."""
        prio_value = -task.priority.value  # negate for min-heap → max-priority
        await self._task_queue.put((prio_value, task.created_at.timestamp(), task))

    # ── Execution Engine ───────────────────────────────────

    async def start(self, worker_count: int = 4) -> None:
        """Start the runtime with worker pool."""
        self._running = True
        logger.info("EvolutionRuntime started with %d workers", worker_count)
        workers = [self._worker(i) for i in range(worker_count)]
        await asyncio.gather(*workers)

    async def stop(self) -> None:
        """Graceful shutdown."""
        self._running = False
        # Cancel pending tasks
        while not self._task_queue.empty():
            _, _, task = await self._task_queue.get()
            task.status = TaskStatus.CANCELLED
        logger.info("EvolutionRuntime stopped")

    async def _worker(self, worker_id: int) -> None:
        """Background worker processing the task queue."""
        while self._running:
            try:
                task = await asyncio.wait_for(self._task_queue.get(), timeout=1.0)
                _, _, task = task
                async with self._semaphore:
                    await self._execute(task)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error("Worker %d error: %s", worker_id, e)

    async def _execute(self, task: EvolutionTask) -> None:
        """Execute a single task."""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)
        self._resources.active_tasks += 1

        try:
            # Rate-limit backtests
            if task.task_type == "backtest":
                async with self._backtest_semaphore:
                    self._resources.backtests_run += 1

            # Placeholder for actual computation
            await asyncio.sleep(0.01)

            task.status = TaskStatus.COMPLETED
            task.result = {"status": "ok"}
        except Exception as e:
            task.error = str(e)
            task.retries += 1
            if task.retries <= task.max_retries:
                task.status = TaskStatus.PENDING
                await self._enqueue(task)
                logger.warning("Task %s retry %d/%d", task.task_id, task.retries, task.max_retries)
            else:
                task.status = TaskStatus.FAILED
                logger.error("Task %s failed: %s", task.task_id, e)
        finally:
            task.completed_at = datetime.now(timezone.utc)
            task.duration_ms = (
                (task.completed_at - task.started_at).total_seconds() * 1000
                if task.started_at
                else 0
            )
            self._resources.active_tasks -= 1
            self._completed_tasks.append(task)

    # ── Monitoring ─────────────────────────────────────────

    def get_queue_stats(self) -> Dict[str, Any]:
        return {
            "queue_size": self._task_queue.qsize(),
            "active_tasks": self._resources.active_tasks,
            "completed_tasks": len(self._completed_tasks),
            "backtests_run": self._resources.backtests_run,
            "gpu_hours_used": self._resources.gpu_hours_used,
        }

    def get_resource_usage(self) -> Dict[str, Any]:
        return {
            "cpu_utilization": self._resources.cpu_utilization,
            "memory_used_gb": self._resources.memory_used_gb,
            "active_tasks": self._resources.active_tasks,
            "max_concurrent": self._resources.max_concurrent_tasks,
        }

    @property
    def is_running(self) -> bool:
        return self._running
