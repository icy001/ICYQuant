"""Priority Scheduler — priority-based job ordering and resource allocation.

The :class:`PriorityScheduler` orders jobs by priority (Critical > High >
Normal > Low) and ensures high-priority jobs get resources first, even in
contended scenarios.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


class Priority:
    """Standard priority levels (lower value = higher urgency)."""

    CRITICAL = 0
    HIGH = 10
    NORMAL = 50
    LOW = 100

    @classmethod
    def label(cls, priority: int) -> str:
        if priority <= cls.CRITICAL:
            return "critical"
        if priority <= cls.HIGH:
            return "high"
        if priority <= cls.NORMAL:
            return "normal"
        return "low"


@dataclass(order=True)
class PrioritizedJob:
    """A job with an assigned priority for scheduling."""

    priority: int
    job_id: str = field(compare=False)
    tenant_id: str = field(compare=False)
    cpu_request: float = field(compare=False, default=0.0)
    memory_request_mb: float = field(compare=False, default=0.0)
    gpu_request: float = field(compare=False, default=0.0)
    age_seconds: float = field(compare=False, default=0.0)


class PriorityScheduler:
    """Orders jobs by priority for resource allocation.

    High-priority jobs skip the queue; low-priority jobs get resources
    only after high-priority demand is satisfied.  An optional starvation
    prevention mechanism promotes long-waiting low-priority jobs.

    Usage::

        sched = PriorityScheduler()
        sched.enqueue(PrioritizedJob(priority=Priority.CRITICAL, job_id="j1", ...))
        sched.enqueue(PrioritizedJob(priority=Priority.LOW, job_id="j2", ...))
        next_job = sched.dequeue()  # j1 (CRITICAL)
    """

    def __init__(self, max_starvation_seconds: float = 300.0) -> None:
        self._max_starvation = max_starvation_seconds
        self._queue: List[PrioritizedJob] = []
        self._completed: int = 0
        self._starved_promoted: int = 0

    # ------------------------------------------------------------------
    # Queue
    # ------------------------------------------------------------------

    def enqueue(self, job: PrioritizedJob) -> None:
        self._queue.append(job)
        self._queue.sort()  # ascending priority

    def dequeue(self) -> Optional[PrioritizedJob]:
        """Return the highest-priority job, applying starvation prevention."""
        if not self._queue:
            return None

        # Check for starved low-priority jobs
        for i, job in enumerate(self._queue):
            if job.age_seconds > self._max_starvation:
                # Promote to high priority
                job.priority = Priority.HIGH
                self._starved_promoted += 1
                self._queue.sort()

        job = self._queue.pop(0)
        self._completed += 1
        return job

    def peek(self) -> Optional[PrioritizedJob]:
        return self._queue[0] if self._queue else None

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def count(self) -> int:
        return len(self._queue)

    def count_by_priority(self) -> Dict[str, int]:
        counts: Dict[str, int] = {"critical": 0, "high": 0, "normal": 0, "low": 0}
        for job in self._queue:
            counts[Priority.label(job.priority)] += 1
        return counts

    def drain(self) -> List[PrioritizedJob]:
        jobs = list(self._queue)
        self._queue.clear()
        return jobs

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        return {
            "queue_depth": len(self._queue),
            "by_priority": self.count_by_priority(),
            "completed": self._completed,
            "starved_promoted": self._starved_promoted,
        }
