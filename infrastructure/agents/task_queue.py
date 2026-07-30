"""Agent Task Queue - prioritized task scheduling for agents."""

import time
import uuid
import heapq
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    LOW = 0
    NORMAL = 5
    HIGH = 10
    CRITICAL = 15


@dataclass
class Task:
    """A unit of work for an agent."""

    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    agent: str = ""
    action: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Any = None
    error: Optional[str] = None
    max_retries: int = 3
    retry_count: int = 0
    timeout: float = 300.0
    callback: Optional[Callable] = None
    dependencies: List[str] = field(default_factory=list)
    _heap_key: float = field(default=0.0)

    def __post_init__(self):
        self._heap_key = -self.priority.value

    def __lt__(self, other: "Task") -> bool:
        if self._heap_key != other._heap_key:
            return self._heap_key < other._heap_key
        return self.created_at < other.created_at

    @property
    def duration(self) -> Optional[float]:
        if self.completed_at and self.started_at:
            return self.completed_at - self.started_at
        return None

    @property
    def is_terminal(self) -> bool:
        return self.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "agent": self.agent,
            "action": self.action,
            "priority": self.priority.name,
            "status": self.status.value,
            "created_at": self.created_at,
            "result": self.result,
            "error": self.error,
        }


class TaskQueue:
    """Priority-based task queue with dependency resolution and retry."""

    def __init__(self, name: str = "default", max_concurrent: int = 10):
        self.name = name
        self.max_concurrent = max_concurrent
        self._heap: List[Task] = []
        self._task_registry: Dict[str, Task] = {}
        self._running: Dict[str, Task] = {}
        self._history: List[Task] = []
        self._max_history = 5000

    def submit(self, task: Task) -> str:
        """Submit a task to the queue."""
        self._task_registry[task.task_id] = task
        if task.status == TaskStatus.PENDING:
            heapq.heappush(self._heap, task)
        logger.debug("Task submitted: %s (%s)", task.task_id, task.name)
        return task.task_id

    def get_next(self) -> Optional[Task]:
        """Get the next pending task that has its dependencies met."""
        if len(self._running) >= self.max_concurrent:
            return None

        # Check dependencies
        temp: List[Task] = []
        next_task = None
        while self._heap:
            task = heapq.heappop(self._heap)
            if task.status != TaskStatus.PENDING:
                continue
            if self._dependencies_met(task):
                next_task = task
                break
            temp.append(task)

        # Re-heap tasks we passed over
        for t in temp:
            heapq.heappush(self._heap, t)

        if next_task:
            next_task.status = TaskStatus.RUNNING
            next_task.started_at = time.time()
            self._running[next_task.task_id] = next_task

        return next_task

    def complete(self, task_id: str, result: Any = None) -> None:
        """Mark a task as completed."""
        task = self._running.pop(task_id, None) or self._task_registry.get(task_id)
        if task:
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            task.result = result
            self._add_history(task)
            if task.callback:
                try:
                    task.callback(task)
                except Exception:
                    logger.exception("Task callback error for %s", task_id)

    def fail(self, task_id: str, error: str) -> None:
        """Mark a task as failed. Retry if applicable."""
        task = self._running.pop(task_id, None) or self._task_registry.get(task_id)
        if task:
            task.retry_count += 1
            if task.retry_count < task.max_retries:
                task.status = TaskStatus.PENDING
                task.error = None
                heapq.heappush(self._heap, task)
                logger.info("Task %s retrying (%d/%d)", task_id, task.retry_count, task.max_retries)
            else:
                task.status = TaskStatus.FAILED
                task.completed_at = time.time()
                task.error = error
                self._add_history(task)
                logger.warning("Task %s failed: %s", task_id, error)

    def cancel(self, task_id: str) -> bool:
        """Cancel a pending or running task."""
        task = self._task_registry.get(task_id)
        if task and not task.is_terminal:
            task.status = TaskStatus.CANCELLED
            task.completed_at = time.time()
            if task_id in self._running:
                del self._running[task_id]
            self._add_history(task)
            return True
        return False

    def _dependencies_met(self, task: Task) -> bool:
        """Check if all dependencies are completed."""
        for dep_id in task.dependencies:
            dep = self._task_registry.get(dep_id)
            if dep is None or dep.status != TaskStatus.COMPLETED:
                return False
        return True

    def _add_history(self, task: Task) -> None:
        self._history.append(task)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._task_registry.get(task_id)

    def get_tasks_by_agent(self, agent: str) -> List[Task]:
        return [t for t in self._task_registry.values() if t.agent == agent]

    def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        return [t for t in self._task_registry.values() if t.status == status]

    @property
    def pending_count(self) -> int:
        return len([t for t in self._task_registry.values() if t.status == TaskStatus.PENDING])

    @property
    def running_count(self) -> int:
        return len(self._running)

    @property
    def queue_size(self) -> int:
        return len(self._heap)

    def clear(self) -> None:
        self._heap.clear()
        self._task_registry.clear()
        self._running.clear()
        self._history.clear()
