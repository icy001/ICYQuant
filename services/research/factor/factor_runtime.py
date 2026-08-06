"""Factor Runtime — orchestrates factor computation and evaluation execution.

Bridges factor research with the Research Platform's runtime, scheduler,
and workflow engine for distributed factor computation.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .factor_context import FactorContext

logger = logging.getLogger(__name__)


class FactorRuntimeState(str, Enum):
    """Factor runtime lifecycle states."""

    IDLE = "idle"
    QUEUED = "queued"
    INITIALIZING = "initializing"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FactorRuntime:
    """Orchestrates factor computation and evaluation execution.

    Responsibilities:
    * Translate factor config into executable pipelines
    * Schedule computation via the Distributed Scheduler
    * Track execution progress and state transitions
    * Handle cancellation and error recovery
    * Collect results for evaluation and alpha pool submission
    """

    def __init__(self, context: Optional[FactorContext] = None) -> None:
        self._runtime_id = str(uuid4())
        self._context = context or FactorContext()
        self._active_computations: Dict[str, Dict[str, Any]] = {}
        self._computation_history: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._state = FactorRuntimeState.IDLE

    @property
    def runtime_id(self) -> str:
        return self._runtime_id

    @property
    def state(self) -> FactorRuntimeState:
        return self._state

    @property
    def active_computations(self) -> Dict[str, Dict[str, Any]]:
        return self._active_computations

    async def submit(
        self,
        factor_id: str,
        dataset: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Submit a factor computation job."""
        async with self._lock:
            job_id = str(uuid4())
            now = datetime.now(timezone.utc)

            job = {
                "job_id": job_id,
                "factor_id": factor_id,
                "dataset": dataset,
                "config": config or {},
                "state": FactorRuntimeState.QUEUED.value,
                "submitted_at": now.isoformat(),
                "started_at": None,
                "completed_at": None,
                "result": None,
                "error": None,
            }

            self._active_computations[job_id] = job
            self._computation_history.append(job)
            self._state = FactorRuntimeState.QUEUED

            logger.info("Factor computation job %s queued for factor %s", job_id, factor_id)
            return job

    async def start(self, job_id: str) -> Dict[str, Any]:
        """Start executing a queued computation job."""
        async with self._lock:
            job = self._active_computations.get(job_id)
            if job is None:
                raise ValueError(f"Job not found: {job_id}")
            if job["state"] != FactorRuntimeState.QUEUED.value:
                raise RuntimeError(f"Job not in queued state: {job['state']}")

            job["state"] = FactorRuntimeState.RUNNING.value
            job["started_at"] = datetime.now(timezone.utc).isoformat()
            self._state = FactorRuntimeState.RUNNING
            logger.info("Factor computation job %s started", job_id)
            return job

    async def complete(
        self, job_id: str, result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Mark a computation job as completed."""
        async with self._lock:
            job = self._active_computations.get(job_id)
            if job is None:
                raise ValueError(f"Job not found: {job_id}")

            job["state"] = FactorRuntimeState.COMPLETED.value
            job["result"] = result
            job["completed_at"] = datetime.now(timezone.utc).isoformat()
            logger.info("Factor computation job %s completed", job_id)
            return job

    async def fail(self, job_id: str, error: str) -> Dict[str, Any]:
        """Mark a computation job as failed."""
        async with self._lock:
            job = self._active_computations.get(job_id)
            if job is None:
                raise ValueError(f"Job not found: {job_id}")

            job["state"] = FactorRuntimeState.FAILED.value
            job["error"] = error
            job["completed_at"] = datetime.now(timezone.utc).isoformat()
            self._state = FactorRuntimeState.FAILED
            logger.error("Factor computation job %s failed: %s", job_id, error)
            return job

    async def cancel(self, job_id: str) -> Dict[str, Any]:
        """Cancel an active computation job."""
        async with self._lock:
            job = self._active_computations.get(job_id)
            if job is None:
                raise ValueError(f"Job not found: {job_id}")

            job["state"] = FactorRuntimeState.CANCELLED.value
            job["completed_at"] = datetime.now(timezone.utc).isoformat()
            logger.info("Factor computation job %s cancelled", job_id)
            return job

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self._active_computations.get(job_id)

    async def list_jobs(
        self, state: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if state:
            return [
                j for j in self._computation_history
                if j.get("state") == state
            ]
        return list(self._computation_history)

    def history_summary(self) -> Dict[str, int]:
        """Summary of computation history by state."""
        counts: Dict[str, int] = {}
        for job in self._computation_history:
            st = job.get("state", "unknown")
            counts[st] = counts.get(st, 0) + 1
        return counts
