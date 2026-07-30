"""
Knowledge Pipeline Infrastructure.

Background pipeline for processing knowledge data:
- Scheduled ingestion
- Batch NLP processing
- Graph maintenance
- Signal generation
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Enums ────────────────────────────────────────────────────────────────────

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class PipelineState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class PipelineTask:
    """A single task in the knowledge pipeline."""

    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    task_type: str = ""  # ingest, nlp, sent, entity, event, graph, embed, signal

    # Input/output
    input_data: Any = None
    output_data: Any = None

    # Execution
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0
    timeout_seconds: float = 300.0
    retry_count: int = 0
    max_retries: int = 3

    # Timing
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0

    # Error
    error: Optional[str] = None
    attempts: int = 0

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskResult:
    """Result of a completed pipeline task."""

    task_id: str = ""
    status: TaskStatus = TaskStatus.COMPLETED
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0


@dataclass
class PipelineConfig:
    """Configuration for the knowledge pipeline."""

    # Concurrency
    max_workers: int = 4
    task_timeout: float = 600.0

    # Scheduling
    check_interval_seconds: float = 1.0
    max_queue_size: int = 10000

    # Retry
    max_retries: int = 3
    retry_delay_seconds: float = 5.0

    # Batching
    batch_size: int = 100

    # Handlers
    auto_start: bool = False


# ── Knowledge Pipeline ───────────────────────────────────────────────────────

class KnowledgePipeline:
    """
    Background pipeline for knowledge data processing.

    Manages task queue, concurrent execution, retry logic,
    and progress tracking for the knowledge processing pipeline.
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()
        self._tasks: Dict[str, PipelineTask] = {}
        self._task_queue: List[str] = []  # IDs ordered by priority
        self._results: Dict[str, TaskResult] = {}
        self._state: PipelineState = PipelineState.IDLE

        # Handlers for each task type
        self._handlers: Dict[str, Callable[[Any], Any]] = {}

        # Execution
        self._executor: Optional[ThreadPoolExecutor] = None
        self._futures: Dict[str, Any] = {}
        self._lock = threading.Lock()

    # ── Task Management ──────────────────────────────────────────────────────

    def submit(
        self,
        task_type: str,
        input_data: Any,
        name: str = "",
        priority: int = 0,
        timeout_seconds: Optional[float] = None,
        **kwargs,
    ) -> str:
        """
        Submit a task to the pipeline.

        Args:
            task_type: Task type (ingest, nlp, sent, entity, event, graph, embed, signal).
            input_data: Input data for the handler.
            name: Human-readable name.
            priority: Higher = processed first.
            timeout_seconds: Task timeout.

        Returns:
            task_id
        """
        with self._lock:
            if len(self._task_queue) >= self.config.max_queue_size:
                raise RuntimeError("Task queue is full")

            task = PipelineTask(
                name=name or task_type,
                task_type=task_type,
                input_data=input_data,
                priority=priority,
                timeout_seconds=timeout_seconds or self.config.task_timeout,
                max_retries=kwargs.get("max_retries", self.config.max_retries),
            )
            self._tasks[task.task_id] = task
            self._task_queue.append(task.task_id)
            # Sort by priority (descending)
            self._task_queue.sort(
                key=lambda tid: self._tasks[tid].priority, reverse=True
            )

        return task.task_id

    def submit_batch(
        self,
        task_type: str,
        inputs: List[Any],
        **kwargs,
    ) -> List[str]:
        """Submit multiple tasks of the same type."""
        return [self.submit(task_type, inp, **kwargs) for inp in inputs]

    def register_handler(
        self, task_type: str, handler: Callable[[Any], Any]
    ) -> None:
        """Register a handler function for a task type."""
        self._handlers[task_type] = handler

    # ── Execution ────────────────────────────────────────────────────────────

    def run(self, max_tasks: Optional[int] = None) -> List[TaskResult]:
        """
        Execute queued tasks sequentially.

        Args:
            max_tasks: Maximum number of tasks to process.

        Returns:
            List of TaskResult objects.
        """
        self._state = PipelineState.RUNNING
        results: List[TaskResult] = []
        processed = 0

        while self._task_queue:
            if max_tasks and processed >= max_tasks:
                break

            if self._state == PipelineState.STOPPED:
                break

            with self._lock:
                if not self._task_queue:
                    break
                task_id = self._task_queue.pop(0)

            task = self._tasks.get(task_id)
            if not task:
                continue

            result = self._execute_task(task)
            results.append(result)
            processed += 1

        self._state = PipelineState.IDLE if self._task_queue else PipelineState.STOPPED
        return results

    def run_async(self, max_tasks: Optional[int] = None) -> None:
        """Execute tasks in a background thread."""
        threading.Thread(
            target=self.run,
            kwargs={"max_tasks": max_tasks},
            daemon=True,
        ).start()

    def run_concurrent(self, max_tasks: Optional[int] = None) -> List[TaskResult]:
        """
        Execute tasks concurrently using thread pool.

        Args:
            max_tasks: Maximum number of tasks to process.

        Returns:
            List of TaskResult objects.
        """
        self._state = PipelineState.RUNNING
        results: List[TaskResult] = []
        executor = ThreadPoolExecutor(max_workers=self.config.max_workers)

        # Collect tasks to process
        with self._lock:
            limit = max_tasks or len(self._task_queue)
            task_ids = self._task_queue[:limit]
            self._task_queue = self._task_queue[limit:]

        futures = {}
        for tid in task_ids:
            task = self._tasks.get(tid)
            if task:
                future = executor.submit(self._execute_task, task)
                futures[future] = tid

        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f"Task {futures[future]} failed: {e}")

        executor.shutdown(wait=False)
        self._state = PipelineState.IDLE
        return results

    def _execute_task(self, task: PipelineTask) -> TaskResult:
        """Execute a single task."""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)
        task.attempts += 1
        start = time.time()

        try:
            handler = self._handlers.get(task.task_type)
            if not handler:
                raise ValueError(f"No handler for task type: {task.task_type}")

            output = handler(task.input_data)
            task.output_data = output
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc)
            task.duration_ms = (time.time() - start) * 1000

            result = TaskResult(
                task_id=task.task_id,
                status=TaskStatus.COMPLETED,
                output=output,
                duration_ms=task.duration_ms,
            )

        except Exception as e:
            logger.error(f"Task {task.task_id} failed (attempt {task.attempts}): {e}")
            task.error = str(e)

            if task.attempts < task.max_retries:
                task.status = TaskStatus.PENDING
                task.retry_count += 1
                # Re-add to queue
                with self._lock:
                    self._task_queue.append(task.task_id)
                result = TaskResult(
                    task_id=task.task_id,
                    status=TaskStatus.PENDING,
                    error=str(e),
                )
            else:
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now(timezone.utc)
                task.duration_ms = (time.time() - start) * 1000
                result = TaskResult(
                    task_id=task.task_id,
                    status=TaskStatus.FAILED,
                    error=str(e),
                    duration_ms=task.duration_ms,
                )

        self._results[task.task_id] = result
        return result

    # ── Control ──────────────────────────────────────────────────────────────

    def pause(self) -> None:
        """Pause the pipeline."""
        self._state = PipelineState.PAUSED

    def resume(self) -> None:
        """Resume the pipeline."""
        self._state = PipelineState.RUNNING

    def stop(self) -> None:
        """Stop the pipeline."""
        self._state = PipelineState.STOPPED

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task."""
        with self._lock:
            if task_id in self._task_queue:
                self._task_queue.remove(task_id)
                if task_id in self._tasks:
                    self._tasks[task_id].status = TaskStatus.CANCELLED
                return True
        return False

    # ── Query ────────────────────────────────────────────────────────────────

    def get_task(self, task_id: str) -> Optional[PipelineTask]:
        """Get task by ID."""
        return self._tasks.get(task_id)

    def get_result(self, task_id: str) -> Optional[TaskResult]:
        """Get task result by ID."""
        return self._results.get(task_id)

    def get_status(self) -> Dict[str, Any]:
        """Get pipeline status summary."""
        status_counts = {
            TaskStatus.PENDING: 0,
            TaskStatus.RUNNING: 0,
            TaskStatus.COMPLETED: 0,
            TaskStatus.FAILED: 0,
            TaskStatus.SKIPPED: 0,
            TaskStatus.CANCELLED: 0,
        }
        for task in self._tasks.values():
            status_counts[task.status] += 1

        return {
            "state": self._state.value,
            "queue_size": len(self._task_queue),
            "total_tasks": len(self._tasks),
            "completed": status_counts[TaskStatus.COMPLETED],
            "failed": status_counts[TaskStatus.FAILED],
            "pending": status_counts[TaskStatus.PENDING],
            "running": status_counts[TaskStatus.RUNNING],
        }

    def clear(self) -> None:
        """Clear all tasks and results."""
        self._tasks.clear()
        self._task_queue.clear()
        self._results.clear()
        self._state = PipelineState.IDLE
