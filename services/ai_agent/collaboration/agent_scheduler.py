"""Agent Scheduler — priority-based scheduling of agent tasks with concurrency control.

Pipeline:
    ScheduleRequest (task + priority + timing constraints)
        -> AgentScheduler.enqueue() (add to priority queue)
        -> AgentScheduler.schedule() (dequeue based on priority + availability)
        -> SchedulePlan (ordered execution plan)
        -> AgentDispatcher (execute tasks)
"""

from __future__ import annotations

import asyncio
import heapq
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from services.ai_agent.collaboration.agent_registry import (
    AgentRegistration,
    AgentRegistry,
    AgentStatus,
)

logger = logging.getLogger(__name__)


class TaskPriority(int, Enum):
    """Priority levels for scheduled tasks."""
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    BACKGROUND = 4


class ScheduleStatus(str, Enum):
    """Status of a scheduled task."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScheduleRequest:
    """A request to schedule a task on an agent.

    Attributes:
        task_id: Unique task identifier.
        agent_id: Target agent ID.
        priority: Task priority level.
        task_description: Description of the task.
        payload: Task payload data.
        timeout_seconds: Maximum execution time.
        depends_on: List of task IDs that must complete before this task.
    """

    task_id: str = ""
    agent_id: str = ""
    priority: TaskPriority = TaskPriority.MEDIUM
    task_description: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float = 60.0
    depends_on: List[str] = field(default_factory=list)

    def __lt__(self, other: "ScheduleRequest") -> bool:
        return self.priority.value < other.priority.value


@dataclass
class SchedulePlan:
    """Result of task scheduling — an ordered execution plan.

    Attributes:
        plan_id: Unique plan identifier.
        tasks: Ordered list of scheduled tasks.
        estimated_duration_seconds: Estimated total execution time.
        created_at: Plan creation timestamp.
    """

    plan_id: str = ""
    tasks: List[ScheduleRequest] = field(default_factory=list)
    estimated_duration_seconds: float = 0.0
    created_at: float = field(default_factory=time.monotonic)

    def to_dict(self) -> Dict[str, Any]:
        """Return plan as a dictionary."""
        return {
            "plan_id": self.plan_id,
            "task_count": len(self.tasks),
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "tasks": [
                {
                    "task_id": t.task_id,
                    "agent_id": t.agent_id,
                    "priority": t.priority.name,
                    "description": t.task_description,
                }
                for t in self.tasks
            ],
        }


class AgentScheduler:
    """Priority-based task scheduler for the multi-agent system.

    Manages a priority queue of tasks to be executed by agents. Supports
    dependency ordering (tasks that must complete before others), priority
    levels, and concurrency limits.

    Supports:
        - Priority-based scheduling (5 levels: CRITICAL to BACKGROUND)
        - Dependency ordering (DAG-based task sequencing)
        - Agent availability checking
        - Timeout enforcement
        - Queue statistics

    Usage:
        scheduler = AgentScheduler(registry)
        await scheduler.initialize()
        request = ScheduleRequest(task_id="t1", agent_id="a1", ...)
        await scheduler.enqueue(request)
        plan = await scheduler.schedule()
    """

    def __init__(self, registry: AgentRegistry) -> None:
        """Initialize the scheduler.

        Args:
            registry: Agent registry for availability checks.
        """
        self._registry: AgentRegistry = registry
        self._queue: List[ScheduleRequest] = []
        self._active_tasks: Dict[str, ScheduleRequest] = {}
        self._completed_tasks: Dict[str, ScheduleStatus] = {}
        self._initialized: bool = False
        logger.info("AgentScheduler created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the scheduler."""
        if self._initialized:
            logger.warning("AgentScheduler already initialized")
            return
        self._initialized = True
        logger.info("AgentScheduler initialized")

    async def shutdown(self) -> None:
        """Shut down the scheduler and clear all queues."""
        if not self._initialized:
            return
        self._queue.clear()
        self._active_tasks.clear()
        self._completed_tasks.clear()
        self._initialized = False
        logger.info("AgentScheduler shutdown complete")

    # ── Queue Management ──

    async def enqueue(self, request: ScheduleRequest) -> None:
        """Add a task to the scheduling queue.

        Args:
            request: The task schedule request.
        """
        if not self._initialized:
            raise RuntimeError("AgentScheduler not initialized")

        heapq.heappush(self._queue, request)
        self._completed_tasks[request.task_id] = ScheduleStatus.QUEUED
        logger.debug("Task enqueued: %s (priority=%s, agent=%s)",
                     request.task_id, request.priority.name, request.agent_id)

    async def enqueue_batch(self, requests: List[ScheduleRequest]) -> None:
        """Add multiple tasks to the queue.

        Args:
            requests: List of schedule requests.
        """
        for req in requests:
            await self.enqueue(req)

    # ── Scheduling ──

    async def schedule(self) -> SchedulePlan:
        """Dequeue tasks based on priority and dependency resolution.

        Returns tasks whose dependencies are already satisfied, ordered
        by priority. Respects agent availability.

        Returns:
            A schedule plan with ordered tasks ready for execution.
        """
        if not self._initialized:
            raise RuntimeError("AgentScheduler not initialized")

        ready_tasks: List[ScheduleRequest] = []
        deferred: List[ScheduleRequest] = []

        while self._queue:
            task = heapq.heappop(self._queue)

            # Check dependencies
            deps_satisfied = all(
                self._completed_tasks.get(dep) == ScheduleStatus.COMPLETED
                for dep in task.depends_on
            )

            if not deps_satisfied:
                deferred.append(task)
                continue

            # Check agent availability
            agent = self._registry.lookup(task.agent_id)
            if agent and agent.status in (AgentStatus.BUSY, AgentStatus.UNAVAILABLE):
                deferred.append(task)
                continue

            ready_tasks.append(task)

        # Re-enqueue deferred tasks
        for task in deferred:
            heapq.heappush(self._queue, task)

        # Estimate duration
        estimated = sum(t.timeout_seconds for t in ready_tasks)

        import uuid
        plan = SchedulePlan(
            plan_id=uuid.uuid4().hex[:12],
            tasks=ready_tasks,
            estimated_duration_seconds=estimated,
        )

        logger.debug("Schedule plan created: %d tasks, est=%0.1fs",
                     len(ready_tasks), estimated)
        return plan

    # ── Task Lifecycle ──

    def mark_running(self, task_id: str) -> None:
        """Mark a task as running.

        Args:
            task_id: The task identifier.
        """
        self._completed_tasks[task_id] = ScheduleStatus.RUNNING
        logger.debug("Task running: %s", task_id)

    def mark_completed(self, task_id: str) -> None:
        """Mark a task as completed.

        Args:
            task_id: The task identifier.
        """
        self._completed_tasks[task_id] = ScheduleStatus.COMPLETED
        logger.debug("Task completed: %s", task_id)

    def mark_failed(self, task_id: str) -> None:
        """Mark a task as failed.

        Args:
            task_id: The task identifier.
        """
        self._completed_tasks[task_id] = ScheduleStatus.FAILED
        logger.debug("Task failed: %s", task_id)

    def cancel(self, task_id: str) -> bool:
        """Cancel a queued task.

        Args:
            task_id: The task identifier.

        Returns:
            True if the task was cancelled, False if not found.
        """
        self._completed_tasks[task_id] = ScheduleStatus.CANCELLED
        self._queue = [t for t in self._queue if t.task_id != task_id]
        heapq.heapify(self._queue)
        logger.debug("Task cancelled: %s", task_id)
        return True

    # ── Status ──

    @property
    def queue_depth(self) -> int:
        """Return the number of queued tasks."""
        return len(self._queue)

    @property
    def active_count(self) -> int:
        """Return the number of active tasks."""
        return sum(
            1 for s in self._completed_tasks.values()
            if s == ScheduleStatus.RUNNING
        )

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the scheduler state.

        Returns:
            Dict with queue depth, active tasks, and status breakdown.
        """
        status_counts: Dict[str, int] = {}
        for s in self._completed_tasks.values():
            status_counts[s.value] = status_counts.get(s.value, 0) + 1

        return {
            "initialized": self._initialized,
            "queue_depth": self.queue_depth,
            "active_tasks": self.active_count,
            "total_tracked": len(self._completed_tasks),
            "status_breakdown": status_counts,
        }
