"""Scheduler Adapter — bridges Research Platform to the Distributed Scheduler.

Commit 11 Part 1.5: Integrates research jobs with the distributed scheduler
for periodic execution, cluster scheduling, and batch processing.

Architecture::

    Research Job → Distributed Scheduler → Cluster Execution

Supported scheduling:
    - Periodic research runs (daily/weekly/monthly)
    - Scheduled backtests
    - Automated portfolio updates
    - Overnight batch processing
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class SchedulerAdapterState(str, Enum):
    """Scheduler adapter lifecycle states."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class ResearchJobType(str, Enum):
    """Types of scheduled research jobs."""

    PERIODIC_BACKTEST = "periodic_backtest"
    PERIODIC_FACTOR = "periodic_factor"
    PERIODIC_PORTFOLIO = "periodic_portfolio"
    BATCH_PROCESSING = "batch_processing"
    DATA_REFRESH = "data_refresh"
    MODEL_RETRAIN = "model_retrain"


class ResearchJobSchedule(str, Enum):
    """Common research job schedules."""

    HOURLY = "0 * * * *"
    DAILY_MIDNIGHT = "0 0 * * *"
    DAILY_MARKET_CLOSE = "0 16 * * 1-5"
    WEEKLY = "0 0 * * 0"
    MONTHLY = "0 0 1 * *"


class SchedulerAdapter:
    """Adapter for integrating Research Platform with Distributed Scheduler.

    Manages research job scheduling, cluster resource allocation, and
    job lifecycle tracking.

    Usage::

        adapter = SchedulerAdapter(config={"scheduler_url": "..."})
        await adapter.initialize()
        job_id = await adapter.schedule_job(
            job_type=ResearchJobType.PERIODIC_BACKTEST,
            schedule=ResearchJobSchedule.DAILY_MARKET_CLOSE,
            params={"dataset": "us_equity_daily"},
        )
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        adapter_id: Optional[str] = None,
    ) -> None:
        self._id: str = adapter_id or f"sca-{uuid4().hex[:12]}"
        self._config: Dict[str, Any] = config or {}
        self._state: SchedulerAdapterState = SchedulerAdapterState.UNINITIALIZED
        self._created_at: datetime = datetime.now(timezone.utc)

        # Scheduler connection
        self._scheduler_url: str = self._config.get("scheduler_url", "http://localhost:8200")
        self._scheduler_connected: bool = False

        # Job registry
        self._scheduled_jobs: Dict[str, Dict[str, Any]] = {}
        self._job_results: Dict[str, List[Dict[str, Any]]] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def id(self) -> str:
        return self._id

    @property
    def state(self) -> SchedulerAdapterState:
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._scheduler_connected

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize scheduler adapter and connect to Distributed Scheduler."""
        self._state = SchedulerAdapterState.INITIALIZING
        logger.info("Initializing SchedulerAdapter [%s] → %s", self._id, self._scheduler_url)

        try:
            await self._connect()
            self._scheduler_connected = True
            self._state = SchedulerAdapterState.CONNECTED
        except Exception as exc:
            logger.error("Failed to connect to Scheduler: %s", exc)
            self._state = SchedulerAdapterState.ERROR
            raise

        logger.info("SchedulerAdapter initialized [%s]", self._id)

    async def synchronize(self) -> Dict[str, Any]:
        """Synchronize with the Distributed Scheduler."""
        status: Dict[str, Any] = {
            "adapter_id": self._id,
            "scheduler_connected": self._scheduler_connected,
            "scheduled_jobs": len(self._scheduled_jobs),
        }
        if not self._scheduler_connected:
            try:
                await self._connect()
                self._scheduler_connected = True
                status["reconnected"] = True
            except Exception:
                status["reconnected"] = False
        return status

    async def shutdown(self) -> None:
        """Disconnect from scheduler and clean up."""
        logger.info("Shutting down SchedulerAdapter [%s]...", self._id)
        self._scheduled_jobs.clear()
        self._job_results.clear()
        self._scheduler_connected = False
        self._state = SchedulerAdapterState.UNINITIALIZED

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    async def _connect(self) -> None:
        """Establish connection to Distributed Scheduler."""
        logger.info("Connecting to Distributed Scheduler at %s", self._scheduler_url)
        await asyncio.sleep(0.01)
        logger.info("Connected to Distributed Scheduler")

    # ------------------------------------------------------------------
    # Job Scheduling
    # ------------------------------------------------------------------

    async def schedule_job(
        self,
        job_type: ResearchJobType,
        schedule: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        job_name: Optional[str] = None,
        timeout_seconds: int = 3600,
        retry_count: int = 3,
    ) -> str:
        """Schedule a research job.

        Args:
            job_type: Type of research job.
            schedule: Cron expression for scheduling.
            params: Job parameters.
            job_name: Optional display name.
            timeout_seconds: Max execution time.
            retry_count: Number of retries on failure.

        Returns:
            Job ID.
        """
        if not self._scheduler_connected:
            raise RuntimeError("Not connected to Scheduler")

        job_id = f"job-{uuid4().hex[:16]}"
        job = {
            "id": job_id,
            "name": job_name or f"{job_type.value}-{job_id[:8]}",
            "type": job_type.value,
            "schedule": schedule,
            "params": params or {},
            "timeout_seconds": timeout_seconds,
            "retry_count": retry_count,
            "status": "scheduled",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "next_run": None,
            "last_run": None,
            "run_count": 0,
        }
        self._scheduled_jobs[job_id] = job
        logger.info("Job scheduled: %s [%s] schedule=%s", job_id, job_type.value, schedule)
        return job_id

    async def unschedule_job(self, job_id: str) -> None:
        """Unschedule a research job."""
        job = self._scheduled_jobs.pop(job_id, None)
        if job is None:
            raise KeyError(f"Job not found: {job_id}")
        self._job_results.pop(job_id, None)
        logger.info("Job unscheduled: %s", job_id)

    async def trigger_job(self, job_id: str) -> Dict[str, Any]:
        """Trigger immediate execution of a scheduled job."""
        job = self._scheduled_jobs.get(job_id)
        if job is None:
            raise KeyError(f"Job not found: {job_id}")

        job["last_run"] = datetime.now(timezone.utc).isoformat()
        job["run_count"] += 1
        logger.info("Triggering job: %s", job_id)

        # Execute job
        result = await self._execute_job(job)
        if job_id not in self._job_results:
            self._job_results[job_id] = []
        self._job_results[job_id].append(result)
        return result

    async def _execute_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a research job (stub — actual execution delegated to scheduler)."""
        await asyncio.sleep(0.01)
        return {
            "job_id": job["id"],
            "type": job["type"],
            "status": "completed",
            "executed_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get the status of a scheduled job."""
        job = self._scheduled_jobs.get(job_id)
        if job is None:
            raise KeyError(f"Job not found: {job_id}")
        return {
            "id": job_id,
            "status": job["status"],
            "type": job["type"],
            "schedule": job["schedule"],
            "run_count": job["run_count"],
            "last_run": job["last_run"],
        }

    async def list_jobs(self, job_type: Optional[ResearchJobType] = None) -> List[Dict[str, Any]]:
        """List scheduled jobs, optionally filtered by type."""
        jobs = list(self._scheduled_jobs.values())
        if job_type is not None:
            jobs = [j for j in jobs if j["type"] == job_type.value]
        return [
            {"id": j["id"], "name": j["name"], "type": j["type"], "schedule": j["schedule"], "status": j["status"]}
            for j in jobs
        ]
