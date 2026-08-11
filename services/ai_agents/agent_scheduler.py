"""
ICYQuant Agent Scheduler — task scheduling and dispatch for multi-agent systems.

Routes tasks to the most suitable agents based on capability matching,
load balancing, and priority-based scheduling.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TaskPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScheduledTask:
    """A task scheduled for agent execution."""
    task_id: str
    description: str
    required_capabilities: list[str] = field(default_factory=list)
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent_id: str = ""
    result: Any = None
    error: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0


class AgentScheduler:
    """Task scheduler for multi-agent systems.

    Responsibilities:
        - Queue and prioritize tasks
        - Match tasks to agents by capability
        - Load balance across available agents
        - Track task lifecycle
    """

    def __init__(self, registry: Any = None) -> None:
        self._registry = registry
        self._tasks: dict[str, ScheduledTask] = {}
        self._queue: list[str] = []  # task_ids ordered by priority
        self._total_dispatched = 0

    def schedule(self, task_id: str, description: str,
                 required_capabilities: Optional[list[str]] = None,
                 priority: TaskPriority = TaskPriority.MEDIUM,
                 metadata: Optional[dict[str, Any]] = None) -> ScheduledTask:
        """Schedule a new task for execution."""
        task = ScheduledTask(
            task_id=task_id,
            description=description,
            required_capabilities=required_capabilities or [],
            priority=priority,
            metadata=metadata or {},
        )
        self._tasks[task_id] = task
        self._enqueue(task_id, priority)
        logger.debug("Scheduled task %s [%s]", task_id, priority.value)
        return task

    def find_best_agent(self, required_capabilities: list[str]) -> Optional[str]:
        """Find the best available agent for a task.

        Strategy: find the agent with the most matching capabilities
        and the lowest current task load.
        """
        if self._registry is None:
            return None

        best_agent_id: Optional[str] = None
        best_score = -1

        for agent_id in self._registry.list_all():
            agent_info = self._registry.get(agent_id)
            if agent_info is None or not hasattr(agent_info, 'capabilities'):
                continue

            agent_caps = set(agent_info.capabilities)
            required_caps = set(required_capabilities)

            if not required_caps or required_caps.issubset(agent_caps):
                match_score = len(agent_caps & required_caps)
                load_penalty = agent_info.task_count * 0.1
                score = match_score - load_penalty

                if score > best_score:
                    best_score = score
                    best_agent_id = agent_id

        return best_agent_id

    def assign_task(self, task_id: str, agent_id: str) -> bool:
        """Assign a queued task to an agent."""
        task = self._tasks.get(task_id)
        if task is None or task.status != TaskStatus.QUEUED:
            return False

        task.assigned_agent_id = agent_id
        task.status = TaskStatus.ASSIGNED
        task.started_at = datetime.now(timezone.utc)

        if self._registry:
            self._registry.increment_task_count(agent_id)

        self._total_dispatched += 1
        return True

    def complete_task(self, task_id: str, result: Any = None) -> bool:
        task = self._tasks.get(task_id)
        if task is None:
            return False
        task.status = TaskStatus.COMPLETED
        task.result = result
        task.completed_at = datetime.now(timezone.utc)
        return True

    def fail_task(self, task_id: str, error: str) -> bool:
        task = self._tasks.get(task_id)
        if task is None:
            return False
        task.status = TaskStatus.FAILED
        task.error = error
        task.completed_at = datetime.now(timezone.utc)
        return True

    def cancel_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task is None:
            return False
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now(timezone.utc)
        return True

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        return self._tasks.get(task_id)

    def get_pending_tasks(self) -> list[ScheduledTask]:
        return [t for t in self._tasks.values() if t.status in (TaskStatus.PENDING, TaskStatus.QUEUED)]

    def _enqueue(self, task_id: str, priority: TaskPriority) -> None:
        priority_order = {TaskPriority.CRITICAL: 0, TaskPriority.HIGH: 1,
                          TaskPriority.MEDIUM: 2, TaskPriority.LOW: 3}
        task = self._tasks.get(task_id)
        if task:
            task.status = TaskStatus.QUEUED
        self._queue.append(task_id)
        self._queue.sort(key=lambda tid: priority_order.get(
            self._tasks[tid].priority if tid in self._tasks else TaskPriority.LOW, 99))

    @property
    def task_count(self) -> int:
        return len(self._tasks)

    @property
    def total_dispatched(self) -> int:
        return self._total_dispatched
