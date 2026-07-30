"""
Pipeline Runner — executes MLOps pipelines in production.

Provides the runtime environment for MLOps pipeline execution:
- Isolated execution context
- Timeout management
- Resource tracking
- Result persistence
- Concurrent execution with worker pool
"""

import enum
import time
import uuid
import threading
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RunnerStatus(str, enum.Enum):
    """Status of a pipeline runner job."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class RunnerJob:
    """A single pipeline runner job."""

    job_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    name: str = ""
    pipeline_type: str = ""

    # Execution
    action: Optional[Callable] = None
    args: tuple = ()
    kwargs: Dict[str, Any] = field(default_factory=dict)

    # State
    status: RunnerStatus = RunnerStatus.QUEUED
    result: Any = None
    error: Optional[str] = None

    # Timing
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    timeout_seconds: float = 3600.0

    # Retry
    retry_count: int = 0
    max_retries: int = 2

    # Priority (higher = runs first)
    priority: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "pipeline_type": self.pipeline_type,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "priority": self.priority,
        }

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        if self.started_at:
            return time.time() - self.started_at
        return None

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            RunnerStatus.COMPLETED, RunnerStatus.FAILED,
            RunnerStatus.TIMED_OUT, RunnerStatus.CANCELLED,
        )


@dataclass
class RunnerConfig:
    """Configuration for the pipeline runner."""

    # Workers
    max_workers: int = 4
    worker_poll_interval: float = 0.1

    # Timeouts
    default_timeout_seconds: float = 3600.0
    max_timeout_seconds: float = 86400.0

    # Queue
    max_queue_size: int = 1000
    queue_strategy: str = "priority"  # priority, fifo

    # Retry
    max_retries: int = 2
    retry_delay_seconds: float = 60.0

    # History
    max_history: int = 1000


# ---------------------------------------------------------------------------
# Pipeline Runner
# ---------------------------------------------------------------------------

class PipelineRunner:
    """Executes MLOps pipeline jobs with a worker pool.

    Manages job queuing, execution, timeout handling, retries,
    and concurrent execution via a configurable worker pool.

    Usage::

        runner = PipelineRunner(config)
        job = runner.submit(
            name="Daily Training",
            pipeline_type="training",
            action=train_fn,
            kwargs={"model_name": "Alpha_v38"},
        )
        runner.start()
        runner.wait_for(job.job_id)
        print(job.result)
    """

    def __init__(self, config: RunnerConfig):
        self.config = config
        self._queue: List[RunnerJob] = []
        self._running: Dict[str, RunnerJob] = {}
        self._completed: Dict[str, RunnerJob] = {}
        self._history: List[RunnerJob] = []

        self._workers: List[threading.Thread] = []
        self._running_flag = False
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._job_complete_event = threading.Event()

        self._on_job_complete: List[Callable] = []
        self._on_job_fail: List[Callable] = []

    # ------------------------------------------------------------------
    # Job Submission
    # ------------------------------------------------------------------

    def submit(
        self,
        name: str,
        pipeline_type: str,
        action: Callable,
        args: Optional[tuple] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        timeout_seconds: Optional[float] = None,
        priority: int = 0,
    ) -> RunnerJob:
        """Submit a pipeline job for execution.

        Args:
            name: Human-readable job name.
            pipeline_type: Type of pipeline (training, evaluation, etc.).
            action: Function to execute.
            args: Positional arguments.
            kwargs: Keyword arguments.
            timeout_seconds: Max execution time.
            priority: Higher = runs first.

        Returns:
            The created RunnerJob.

        Raises:
            ValueError: If queue is full.
        """
        with self._lock:
            if len(self._queue) >= self.config.max_queue_size:
                raise ValueError(f"Queue full ({self.config.max_queue_size})")

            job = RunnerJob(
                name=name,
                pipeline_type=pipeline_type,
                action=action,
                args=args or (),
                kwargs=kwargs or {},
                timeout_seconds=timeout_seconds or self.config.default_timeout_seconds,
                priority=priority,
            )
            self._queue.append(job)

            # Sort by priority (higher first)
            if self.config.queue_strategy == "priority":
                self._queue.sort(key=lambda j: j.priority, reverse=True)

        logger.info(f"Job submitted: {name} ({job.job_id}), priority={priority}")
        return job

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the worker pool."""
        if self._running_flag:
            return

        self._running_flag = True
        self._stop_event.clear()

        for i in range(self.config.max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name=f"pipeline-worker-{i}",
            )
            worker.start()
            self._workers.append(worker)

        logger.info(f"PipelineRunner started with {self.config.max_workers} workers")

    def stop(self) -> None:
        """Stop the worker pool."""
        self._stop_event.set()
        for worker in self._workers:
            worker.join(timeout=5.0)
        self._workers.clear()
        self._running_flag = False
        logger.info("PipelineRunner stopped")

    # ------------------------------------------------------------------
    # Worker Loop
    # ------------------------------------------------------------------

    def _worker_loop(self) -> None:
        """Main worker loop."""
        while not self._stop_event.is_set():
            job: Optional[RunnerJob] = None

            with self._lock:
                if self._queue:
                    job = self._queue.pop(0)

            if job:
                self._execute_job(job)
            else:
                self._stop_event.wait(timeout=self.config.worker_poll_interval)

    def _execute_job(self, job: RunnerJob) -> None:
        """Execute a single job."""
        job.status = RunnerStatus.RUNNING
        job.started_at = time.time()

        with self._lock:
            self._running[job.job_id] = job

        logger.debug(f"Executing job: {job.name} ({job.job_id})")

        try:
            # Execute with timeout
            result = self._run_with_timeout(job)
            job.result = result
            job.status = RunnerStatus.COMPLETED
            job.completed_at = time.time()

            logger.info(
                f"Job {job.name} completed in {job.duration_seconds:.2f}s"
            )
            self._notify_complete(job)

        except TimeoutError:
            job.status = RunnerStatus.TIMED_OUT
            job.error = f"Timed out after {job.timeout_seconds}s"
            job.completed_at = time.time()
            logger.error(f"Job {job.name} timed out")
            self._notify_fail(job)

        except Exception as e:
            job.error = str(e)
            logger.error(f"Job {job.name} failed: {e}")

            # Retry
            if job.retry_count < job.max_retries:
                job.retry_count += 1
                logger.info(
                    f"Retrying job {job.name} ({job.retry_count}/{job.max_retries})"
                )
                time.sleep(self.config.retry_delay_seconds * 0.001)
                self._execute_job(job)
                return

            job.status = RunnerStatus.FAILED
            job.completed_at = time.time()
            self._notify_fail(job)

        finally:
            with self._lock:
                self._running.pop(job.job_id, None)
                self._completed[job.job_id] = job

            self._history.append(job)
            self._job_complete_event.set()

            # Trim history
            if len(self._history) > self.config.max_history:
                self._history = self._history[-self.config.max_history:]

    def _run_with_timeout(self, job: RunnerJob) -> Any:
        """Execute a job's action with timeout using a thread."""
        result_container: List[Any] = []
        error_container: List[Optional[Exception]] = [None]

        def target():
            try:
                result_container.append(
                    job.action(*job.args, **job.kwargs)
                )
            except Exception as e:
                error_container[0] = e

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join(timeout=job.timeout_seconds)

        if thread.is_alive():
            raise TimeoutError(f"Job timed out after {job.timeout_seconds}s")

        if error_container[0]:
            raise error_container[0]

        return result_container[0] if result_container else None

    # ------------------------------------------------------------------
    # Waiting & Queries
    # ------------------------------------------------------------------

    def wait_for(self, job_id: str, timeout: Optional[float] = None) -> RunnerJob:
        """Wait for a specific job to complete.

        Args:
            job_id: Job ID to wait for.
            timeout: Max wait time in seconds.

        Returns:
            The completed RunnerJob.

        Raises:
            TimeoutError: If job doesn't complete within timeout.
        """
        start = time.time()
        while True:
            job = self.get_job(job_id)
            if job and job.is_terminal:
                return job

            if timeout and (time.time() - start) > timeout:
                raise TimeoutError(f"Timeout waiting for job {job_id}")

            self._job_complete_event.wait(timeout=1.0)
            self._job_complete_event.clear()

    def wait_all(self, timeout: Optional[float] = None) -> None:
        """Wait for all queued and running jobs to complete."""
        start = time.time()
        while True:
            with self._lock:
                if not self._queue and not self._running:
                    return

            if timeout and (time.time() - start) > timeout:
                raise TimeoutError("Timeout waiting for all jobs")

            self._job_complete_event.wait(timeout=1.0)
            self._job_complete_event.clear()

    def get_job(self, job_id: str) -> Optional[RunnerJob]:
        """Get a job by ID (checks all states)."""
        with self._lock:
            # Check running
            if job_id in self._running:
                return self._running[job_id]
            # Check completed
            if job_id in self._completed:
                return self._completed[job_id]
            # Check queue
            for job in self._queue:
                if job.job_id == job_id:
                    return job
        return None

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a queued job."""
        with self._lock:
            for i, job in enumerate(self._queue):
                if job.job_id == job_id:
                    job.status = RunnerStatus.CANCELLED
                    self._queue.pop(i)
                    self._completed[job_id] = job
                    return True
        return False

    def get_queue_size(self) -> int:
        """Get current queue size."""
        return len(self._queue)

    def get_running_count(self) -> int:
        """Get count of currently running jobs."""
        return len(self._running)

    def list_jobs(
        self,
        status: Optional[RunnerStatus] = None,
        pipeline_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[RunnerJob]:
        """List jobs with filters."""
        jobs = list(self._history)
        if status:
            jobs = [j for j in jobs if j.status == status]
        if pipeline_type:
            jobs = [j for j in jobs if j.pipeline_type == pipeline_type]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)[:limit]

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_complete(self, callback: Callable) -> None:
        """Register a callback for job completion."""
        self._on_job_complete.append(callback)

    def on_fail(self, callback: Callable) -> None:
        """Register a callback for job failure."""
        self._on_job_fail.append(callback)

    def _notify_complete(self, job: RunnerJob) -> None:
        for cb in self._on_job_complete:
            try:
                cb(job)
            except Exception as e:
                logger.error(f"Complete callback error: {e}")

    def _notify_fail(self, job: RunnerJob) -> None:
        for cb in self._on_job_fail:
            try:
                cb(job)
            except Exception as e:
                logger.error(f"Fail callback error: {e}")

    def reset(self) -> None:
        """Reset state (for testing)."""
        self.stop()
        self._queue.clear()
        self._running.clear()
        self._completed.clear()
        self._history.clear()
