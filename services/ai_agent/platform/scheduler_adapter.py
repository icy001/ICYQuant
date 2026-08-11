"""Scheduler Adapter — bridges the AI Platform to the ICYQuant Distributed Scheduler.

The SchedulerAdapter allows AI agents to schedule recurring tasks, one-time
jobs, and cron-style executions through the Distributed Scheduler. It handles
job submission, status monitoring, and result retrieval.

Capabilities:
    - Schedule one-time jobs
    - Schedule recurring jobs (cron)
    - Job status monitoring
    - Job cancellation
    - Result retrieval
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Scheduled job status."""
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScheduledJob:
    """A job scheduled through the Distributed Scheduler."""
    job_id: str = ""
    agent_id: str = ""
    job_type: str = ""
    cron_expression: Optional[str] = None
    scheduled_at: Optional[float] = None
    status: JobStatus = JobStatus.SCHEDULED
    params: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.monotonic)
    last_run: Optional[float] = None
    run_count: int = 0
    max_runs: Optional[int] = None


class SchedulerAdapter:
    """Adapter for the ICYQuant Distributed Scheduler.

    Enables AI agents to schedule tasks through the platform's distributed
    scheduler for one-time and recurring execution.

    Usage:
        sa = SchedulerAdapter()
        await sa.initialize()
        job = await sa.schedule_job(agent_id="agent_1", job_type="market_scan", cron="*/5 * * * *")
    """

    def __init__(self) -> None:
        self._jobs: Dict[str, ScheduledJob] = {}
        self._job_history: List[ScheduledJob] = []
        self._max_history: int = 5000
        self._total_scheduled: int = 0
        self._initialized: bool = False
        logger.info("SchedulerAdapter created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("SchedulerAdapter initialized")

    async def shutdown(self) -> None:
        self._jobs.clear()
        self._job_history.clear()
        self._initialized = False
        logger.info("SchedulerAdapter shutdown complete")

    async def schedule_job(self, agent_id: str, job_type: str, params: Optional[Dict[str, Any]] = None, cron_expression: Optional[str] = None, scheduled_at: Optional[float] = None, max_runs: Optional[int] = None) -> ScheduledJob:
        """Schedule a job for execution.

        Args:
            agent_id: The AI agent requesting the schedule.
            job_type: Type of job to schedule.
            params: Parameters for the job.
            cron_expression: Cron expression for recurring jobs.
            scheduled_at: Timestamp for one-time jobs.
            max_runs: Maximum number of runs for recurring jobs.
        """
        self._total_scheduled += 1
        job_id = f"job_{self._total_scheduled}"

        job = ScheduledJob(
            job_id=job_id,
            agent_id=agent_id,
            job_type=job_type,
            cron_expression=cron_expression,
            scheduled_at=scheduled_at,
            params=params or {},
            max_runs=max_runs,
        )

        self._jobs[job_id] = job
        logger.info("SchedulerAdapter: scheduled job %s (%s, cron=%s) by agent %s", job_id, job_type, cron_expression, agent_id)
        return job

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a scheduled job."""
        job = self._jobs.get(job_id)
        if job and job.status in (JobStatus.SCHEDULED, JobStatus.RUNNING):
            job.status = JobStatus.CANCELLED
            self._job_history.append(job)
            del self._jobs[job_id]
            logger.info("SchedulerAdapter: cancelled job %s", job_id)
            return True
        return False

    async def get_job_status(self, job_id: str) -> Optional[JobStatus]:
        """Get the current status of a scheduled job."""
        job = self._jobs.get(job_id)
        if job:
            return job.status
        for j in self._job_history:
            if j.job_id == job_id:
                return j.status
        return None

    async def list_agent_jobs(self, agent_id: str) -> List[ScheduledJob]:
        """List all jobs for an agent."""
        return [j for j in self._jobs.values() if j.agent_id == agent_id]

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "total_scheduled": self._total_scheduled,
            "active_jobs": len(self._jobs),
            "completed_jobs": len(self._job_history),
        }
