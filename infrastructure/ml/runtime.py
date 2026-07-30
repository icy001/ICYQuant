"""ML Runtime - Unified job execution engine.

Manages training, inference, batch, and online jobs with a consistent
interface. Supports GPU, Docker, and Kubernetes for production scaling.

The current implementation provides an in-process runtime suitable for
development and testing. Production deployments will integrate with
Docker/Kubernetes for distributed execution.

Usage::

    from infrastructure.ml.runtime import MLRuntime, RuntimeJob, JobType

    runtime = MLRuntime()
    job = runtime.submit(JobType.TRAINING, "alpha_model", train_fn)
    runtime.wait(job.id)
    result = runtime.get_result(job.id)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum
from threading import Lock, Thread


class JobType(str, Enum):
    """Type of ML runtime job."""

    TRAINING = "training"
    INFERENCE = "inference"
    BATCH = "batch"
    ONLINE = "online"


class JobStatus(str, Enum):
    """Runtime job status."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


@dataclass
class RuntimeJob:
    """A job submitted to the ML runtime.

    Attributes:
        id: Unique job ID.
        job_type: Type of ML job.
        name: Human-readable name.
        task: Callable to execute.
        args: Positional arguments for task.
        kwargs: Keyword arguments for task.
        status: Current job status.
        result: Result from successful execution.
        error: Error message from failed execution.
        submitted_at: Submission timestamp.
        started_at: Start timestamp.
        finished_at: Completion timestamp.
        timeout_seconds: Maximum execution time.
        retries: Number of retry attempts.
        max_retries: Maximum retry attempts.
        tags: Arbitrary key-value tags.
    """

    id: str = ""
    job_type: JobType = JobType.TRAINING
    name: str = ""
    task: Optional[Callable[..., Any]] = None
    args: tuple = ()
    kwargs: Dict[str, Any] = field(default_factory=dict)
    status: JobStatus = JobStatus.QUEUED
    result: Any = None
    error: str = ""
    submitted_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    timeout_seconds: int = 3600
    retries: int = 0
    max_retries: int = 3
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "job_type": self.job_type.value,
            "name": self.name,
            "status": self.status.value,
            "result": str(self.result)[:200] if self.result else None,
            "error": self.error,
            "submitted_at": self.submitted_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "timeout_seconds": self.timeout_seconds,
            "retries": self.retries,
            "max_retries": self.max_retries,
            "tags": dict(self.tags),
        }

    @property
    def duration_seconds(self) -> Optional[float]:
        """Job duration in seconds, or None if not finished."""
        if self.finished_at and self.started_at:
            return self.finished_at - self.started_at
        if self.started_at:
            return time.time() - self.started_at
        return None


class MLRuntime:
    """Unified ML job runtime.

    Manages the lifecycle of ML jobs (training, inference, batch, online)
    with submission, monitoring, cancellation, and result retrieval.

    In the current development implementation, jobs run in-process.
    Production deployments will integrate with Docker/Kubernetes for
    GPU-accelerated distributed training and inference.

    Usage::

        runtime = MLRuntime()
        job = runtime.submit(
            JobType.TRAINING,
            "train_alpha_model",
            train_model,
            dataset="US_STOCKS_2025",
        )
        runtime.wait(job.id, timeout=3600)
        result = runtime.get_result(job.id)
    """

    def __init__(self) -> None:
        self._jobs: Dict[str, RuntimeJob] = {}
        self._counter: int = 0
        self._lock = Lock()
        self._thread_pool: Dict[str, Thread] = {}

    # ---- Submit ----

    def submit(
        self,
        job_type: JobType,
        name: str,
        task: Callable[..., Any],
        *args: Any,
        timeout_seconds: int = 3600,
        max_retries: int = 3,
        tags: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> RuntimeJob:
        """Submit a job to the runtime for immediate execution.

        Args:
            job_type: Type of ML job.
            name: Human-readable name.
            task: Callable to execute.
            *args: Positional arguments for the task.
            timeout_seconds: Max execution time.
            max_retries: Max retries on failure.
            tags: Key-value tags.
            **kwargs: Keyword arguments for the task.

        Returns:
            The RuntimeJob.
        """
        with self._lock:
            self._counter += 1
            job = RuntimeJob(
                id=f"rt_{self._counter:06d}",
                job_type=job_type,
                name=name,
                task=task,
                args=args,
                kwargs=kwargs,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
                tags=dict(tags or {}),
            )
            self._jobs[job.id] = job

        # Execute asynchronously in a thread
        thread = Thread(target=self._execute_job, args=(job,), daemon=True)
        self._thread_pool[job.id] = thread
        thread.start()
        return job

    def submit_batch(
        self,
        jobs: List[Dict[str, Any]],
    ) -> List[RuntimeJob]:
        """Submit multiple jobs in batch.

        Each dict must have: job_type, name, task.
        Optional: args, kwargs, timeout_seconds, max_retries, tags.
        """
        results = []
        for spec in jobs:
            job = self.submit(
                job_type=JobType(spec["job_type"]) if not isinstance(spec["job_type"], JobType) else spec["job_type"],
                name=spec["name"],
                task=spec["task"],
                args=tuple(spec.get("args", ())),
                timeout_seconds=spec.get("timeout_seconds", 3600),
                max_retries=spec.get("max_retries", 3),
                tags=spec.get("tags"),
                **spec.get("kwargs", {}),
            )
            results.append(job)
        return results

    # ---- Monitor ----

    def get_job(self, job_id: str) -> Optional[RuntimeJob]:
        """Get a job by ID."""
        return self._jobs.get(job_id)

    def get_result(self, job_id: str) -> Any:
        """Get the result of a completed job.

        Returns result for completed jobs, raises RuntimeError for failed jobs.
        """
        job = self._jobs.get(job_id)
        if not job:
            return None
        if job.status == JobStatus.FAILED:
            raise RuntimeError(f"Job '{job.name}' failed: {job.error}")
        if job.status != JobStatus.COMPLETED:
            raise RuntimeError(f"Job '{job.name}' is not complete (status: {job.status.value})")
        return job.result

    def wait(self, job_id: str, timeout: Optional[float] = None) -> bool:
        """Wait for a job to complete.

        Args:
            job_id: Job ID.
            timeout: Max seconds to wait. None means no timeout.

        Returns:
            True if completed, False if timed out.
        """
        job = self._jobs.get(job_id)
        if not job:
            return False
        thread = self._thread_pool.get(job_id)
        if thread:
            thread.join(timeout=timeout)
        return job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.TIMED_OUT, JobStatus.CANCELLED)

    def wait_all(self, timeout: Optional[float] = None) -> Dict[str, bool]:
        """Wait for all submitted jobs to complete.

        Returns:
            {job_id: completed}
        """
        results = {}
        for job_id, thread in list(self._thread_pool.items()):
            thread.join(timeout=timeout)
            job = self._jobs.get(job_id)
            if job:
                results[job_id] = job.status in (JobStatus.COMPLETED, JobStatus.FAILED)
        return results

    # ---- Control ----

    def cancel(self, job_id: str) -> bool:
        """Cancel a queued or running job."""
        job = self._jobs.get(job_id)
        if not job:
            return False
        if job.status in (JobStatus.QUEUED, JobStatus.RUNNING):
            job.status = JobStatus.CANCELLED
            job.finished_at = time.time()
            return True
        return False

    # ---- List ----

    def list_jobs(
        self,
        job_type: Optional[JobType] = None,
        status: Optional[JobStatus] = None,
        limit: int = 100,
    ) -> List[RuntimeJob]:
        """List jobs with optional filters."""
        results = list(self._jobs.values())
        if job_type:
            results = [j for j in results if j.job_type == job_type]
        if status:
            results = [j for j in results if j.status == status]
        results.sort(key=lambda j: j.submitted_at, reverse=True)
        return results[:limit]

    def list_training_jobs(self) -> List[RuntimeJob]:
        """List all training jobs."""
        return self.list_jobs(job_type=JobType.TRAINING)

    def list_inference_jobs(self) -> List[RuntimeJob]:
        """List all inference jobs."""
        return self.list_jobs(job_type=JobType.INFERENCE)

    # ---- Stats ----

    def stats(self) -> Dict[str, Any]:
        """Get runtime statistics."""
        jobs = list(self._jobs.values())
        return {
            "total_jobs": len(jobs),
            "by_type": {
                jt.value: sum(1 for j in jobs if j.job_type == jt)
                for jt in JobType
            },
            "by_status": {
                js.value: sum(1 for j in jobs if j.status == js)
                for js in JobStatus
            },
            "total_training": sum(1 for j in jobs if j.job_type == JobType.TRAINING),
            "total_inference": sum(1 for j in jobs if j.job_type == JobType.INFERENCE),
            "total_batch": sum(1 for j in jobs if j.job_type == JobType.BATCH),
            "total_online": sum(1 for j in jobs if j.job_type == JobType.ONLINE),
        }

    # ---- Internal ----

    def _execute_job(self, job: RuntimeJob) -> None:
        """Execute a job with retry logic."""
        job.status = JobStatus.RUNNING
        job.started_at = time.time()

        for attempt in range(job.max_retries + 1):
            if job.status == JobStatus.CANCELLED:
                return

            try:
                if job.task is None:
                    raise ValueError("Job task is None")

                result = job.task(*job.args, **job.kwargs)
                job.result = result
                job.status = JobStatus.COMPLETED
                job.finished_at = time.time()
                return
            except Exception as e:
                job.retries = attempt
                if attempt < job.max_retries:
                    time.sleep(min(60 * (attempt + 1), 600))
                else:
                    job.error = str(e)
                    job.status = JobStatus.FAILED
                    job.finished_at = time.time()
                    return
