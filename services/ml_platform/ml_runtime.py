"""
ICYQuant ML Runtime - Model execution environment.

Provides lifecycle management for training jobs, inference sessions,
and pipeline executions with concurrency control.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Runtime Enums
# ---------------------------------------------------------------------------


class RuntimeState(Enum):
    """Runtime lifecycle states."""

    CREATED = auto()
    STARTING = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPING = auto()
    STOPPED = auto()
    FAILED = auto()


class JobType(Enum):
    """Types of ML jobs."""

    FEATURE_COMPUTATION = "feature_computation"
    FEATURE_VALIDATION = "feature_validation"
    TRAINING = "training"
    EVALUATION = "evaluation"
    HYPERPARAMETER_SEARCH = "hyperparameter_search"
    CROSS_VALIDATION = "cross_validation"
    INFERENCE = "inference"
    DRIFT_CHECK = "drift_check"
    DATA_EXPORT = "data_export"


class JobPriority(Enum):
    """Job priority levels."""

    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    BACKGROUND = 4


# ---------------------------------------------------------------------------
# Job / Run
# ---------------------------------------------------------------------------


@dataclass
class MLJob:
    """A single ML job to be executed by the runtime."""

    job_id: str = field(default_factory=lambda: uuid4().hex[:12])
    job_type: JobType = JobType.TRAINING
    priority: JobPriority = JobPriority.MEDIUM
    state: RuntimeState = RuntimeState.CREATED

    # Execution
    target: Optional[Callable] = None
    args: tuple = ()
    kwargs: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 3600

    # Metadata
    tags: Dict[str, str] = field(default_factory=dict)
    parent_job_id: Optional[str] = None

    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0

    # Result
    result: Any = None
    error: Optional[str] = None


@dataclass
class RunContext:
    """Context for a single training/inference run."""

    run_id: str = field(default_factory=lambda: uuid4().hex[:12])
    experiment_id: Optional[str] = None
    model_id: Optional[str] = None
    dataset_id: Optional[str] = None

    parameters: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    artifacts: List[str] = field(default_factory=list)

    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# ML Runtime
# ---------------------------------------------------------------------------


class MLRuntime:
    """ML execution runtime with concurrency control.

    Manages parallel training jobs, feature computations, and inference
    sessions with configurable concurrency limits.
    """

    def __init__(
        self,
        max_concurrent_jobs: int = 10,
        max_concurrent_training: int = 5,
        max_concurrent_inference: int = 20,
    ) -> None:
        self._max_concurrent = max_concurrent_jobs
        self._semaphore = asyncio.Semaphore(max_concurrent_jobs)

        self._training_semaphore = asyncio.Semaphore(max_concurrent_training)
        self._inference_semaphore = asyncio.Semaphore(max_concurrent_inference)

        self._active_jobs: Dict[str, MLJob] = {}
        self._job_history: List[MLJob] = []
        self._job_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()

        self._state = RuntimeState.CREATED
        self._started_at: Optional[datetime] = None

    # -- Lifecycle --

    async def start(self) -> None:
        """Start the runtime and begin processing queued jobs."""
        self._state = RuntimeState.STARTING
        self._started_at = datetime.utcnow()
        self._state = RuntimeState.RUNNING
        logger.info("ML Runtime started (max_concurrent=%d)", self._max_concurrent)

    async def stop(self) -> None:
        """Stop the runtime and wait for active jobs to complete."""
        self._state = RuntimeState.STOPPING
        logger.info("ML Runtime stopping (active_jobs=%d)", len(self._active_jobs))
        self._state = RuntimeState.STOPPED

    # -- Job Submission --

    async def submit_job(self, job: MLJob) -> MLJob:
        """Submit a job for execution. Returns immediately with job reference."""
        job.state = RuntimeState.CREATED
        await self._job_queue.put((job.priority.value, job.job_id, job))
        self._active_jobs[job.job_id] = job
        logger.debug("Job submitted: %s (type=%s, priority=%s)", job.job_id, job.job_type.value, job.priority.name)
        return job

    async def submit_training(self, target: Callable, *args: Any, **kwargs: Any) -> MLJob:
        """Submit a training job (uses training-specific semaphore)."""
        job = MLJob(job_type=JobType.TRAINING, target=target, args=args, kwargs=kwargs)
        return await self.submit_job(job)

    async def submit_inference(self, target: Callable, *args: Any, **kwargs: Any) -> MLJob:
        """Submit an inference job."""
        job = MLJob(job_type=JobType.INFERENCE, target=target, args=args, kwargs=kwargs)
        return await self.submit_job(job)

    # -- Job Execution --

    async def execute_job(self, job: MLJob) -> Any:
        """Execute a single job with timeout and error handling."""
        sem = self._training_semaphore if job.job_type == JobType.TRAINING else self._semaphore
        if job.job_type == JobType.INFERENCE:
            sem = self._inference_semaphore

        async with sem:
            job.state = RuntimeState.RUNNING
            job.started_at = datetime.utcnow()

            try:
                if job.target is None:
                    raise ValueError(f"Job {job.job_id} has no target callable")

                result = await asyncio.wait_for(
                    asyncio.coroutine(job.target(*job.args, **job.kwargs))
                    if asyncio.iscoroutinefunction(job.target)
                    else asyncio.to_thread(job.target, *job.args, **job.kwargs),
                    timeout=job.timeout_seconds,
                )

                job.result = result
                job.state = RuntimeState.STOPPED
                return result

            except asyncio.TimeoutError:
                job.state = RuntimeState.FAILED
                job.error = f"Job timed out after {job.timeout_seconds}s"
                logger.error("Job %s timed out", job.job_id)
                raise

            except Exception as exc:
                job.state = RuntimeState.FAILED
                job.error = str(exc)
                logger.exception("Job %s failed: %s", job.job_id, exc)
                raise

            finally:
                job.completed_at = datetime.utcnow()
                if job.started_at:
                    job.duration_seconds = (job.completed_at - job.started_at).total_seconds()
                self._job_history.append(job)

    # -- Status --

    def get_active_jobs(self) -> List[MLJob]:
        """Get currently active (non-terminal) jobs."""
        return [
            j for j in self._active_jobs.values()
            if j.state in (RuntimeState.CREATED, RuntimeState.STARTING, RuntimeState.RUNNING)
        ]

    def get_job(self, job_id: str) -> Optional[MLJob]:
        """Get a job by ID."""
        return self._active_jobs.get(job_id)

    @property
    def active_count(self) -> int:
        return len(self.get_active_jobs())

    @property
    def state(self) -> RuntimeState:
        return self._state
