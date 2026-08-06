"""Scheduler Runtime — the execution engine for the distributed scheduler.

The :class:`SchedulerRuntime` bridges scheduler definitions with live
execution. It manages the trigger→queue→dispatch→workflow pipeline
and delegates to the runtime subsystem for context, events, and metrics.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .models.schedule import ScheduleDefinition, ScheduleStatus
from .models.job import JobDefinition, JobState
from .models.execution import ExecutionRecord, ExecutionState, ExecutionResult
from .runtime import (
    RuntimeManager,
    RuntimeStateManager,
    RuntimePhase,
    SchedulerContext,
    SchedulerEventBus,
    SchedulerEventType,
    SchedulerEvent,
    RuntimeMetricsCollector,
    RuntimeHealthChecker,
    RuntimeScheduler,
)

logger = logging.getLogger(__name__)


class SchedulerRuntime:
    """Execution engine for the distributed scheduler.

    Provides the complete runtime for schedule evaluation, job creation,
    queue management, dispatch, and coordination with the workflow engine.

    Usage::

        runtime = SchedulerRuntime(registry, repository, manager)
        await runtime.start()
        await runtime.enqueue_job(job)
    """

    def __init__(
        self,
        registry: Any = None,
        repository: Any = None,
        manager: Any = None,
    ) -> None:
        self._lock = threading.RLock()
        self._registry = registry
        self._repository = repository
        self._manager = manager

        # Runtime subsystems
        self._runtime_mgr = RuntimeManager()
        self._event_bus = SchedulerEventBus()
        self._metrics = RuntimeMetricsCollector()
        self._health = RuntimeHealthChecker()
        self._loop = RuntimeScheduler()

        # Contexts
        self._contexts: Dict[str, SchedulerContext] = {}
        self._jobs: Dict[str, JobDefinition] = {}
        self._executions: Dict[str, ExecutionRecord] = {}

        # Running state
        self._running: bool = False
        self._paused: bool = False
        self._started_at: Optional[datetime] = None

    # ── lifecycle ──────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the scheduler runtime."""
        with self._lock:
            if self._running:
                return
            self._running = True

        self._started_at = datetime.now(timezone.utc)
        self._event_bus.start()

        # Wire up the runtime scheduler hooks
        self._loop.on_trigger(self._evaluate_triggers)
        self._loop.on_dispatch(self._dispatch_job)

        await self._runtime_mgr.start()
        await self._loop.start()

        self._publish_event(SchedulerEventType.RUNTIME_STARTED, "system")
        logger.info("SchedulerRuntime: started")

    async def stop(self) -> None:
        """Stop the scheduler runtime gracefully."""
        with self._lock:
            if not self._running:
                return
            self._running = False

        self._publish_event(SchedulerEventType.RUNTIME_STOPPED, "system")
        await self._loop.stop()
        await self._runtime_mgr.stop()
        self._event_bus.stop()

        logger.info("SchedulerRuntime: stopped")

    async def pause(self) -> None:
        """Pause scheduling."""
        self._loop.pause()
        self._paused = True
        self._publish_event(SchedulerEventType.RUNTIME_PAUSED, "system")

    async def resume(self) -> None:
        """Resume scheduling."""
        self._loop.resume()
        self._paused = False
        self._publish_event(SchedulerEventType.RUNTIME_RESUMED, "system")

    # ── schedule lifecycle handlers ────────────────────────────────────────

    async def on_schedule_registered(self, schedule: ScheduleDefinition) -> None:
        """Handle schedule registration."""
        self._publish_event(
            SchedulerEventType.SCHEDULE_CREATED, schedule.schedule_id,
            data=schedule.to_dict(),
        )

    async def on_schedule_paused(self, schedule: ScheduleDefinition) -> None:
        """Handle schedule pause."""
        self._publish_event(
            SchedulerEventType.SCHEDULE_PAUSED, schedule.schedule_id,
        )

    async def on_schedule_resumed(self, schedule: ScheduleDefinition) -> None:
        """Handle schedule resume."""
        self._publish_event(
            SchedulerEventType.SCHEDULE_RESUMED, schedule.schedule_id,
        )

    async def on_schedule_removed(self, schedule: ScheduleDefinition) -> None:
        """Handle schedule removal."""
        self._publish_event(
            SchedulerEventType.SCHEDULE_REMOVED, schedule.schedule_id,
        )

    # ── job management ─────────────────────────────────────────────────────

    async def enqueue_job(self, job: JobDefinition) -> bool:
        """Enqueue a job for execution."""
        queued = job.transition_to(JobState.QUEUED)
        with self._lock:
            self._jobs[queued.job_id] = queued
        success = self._loop.enqueue(queued)
        if success:
            self._metrics.jobs_total.inc()
            self._metrics.queue_size.set(float(self._loop.queue_length))
            self._publish_event(
                SchedulerEventType.JOB_QUEUED,
                job.schedule_id,
                job_id=job.job_id,
            )
        return success

    def get_job(self, job_id: str) -> Optional[JobDefinition]:
        """Retrieve a job by ID."""
        return self._jobs.get(job_id)

    def list_jobs(self, limit: int = 100) -> List[JobDefinition]:
        """List active jobs."""
        jobs = list(self._jobs.values())
        return jobs[:limit]

    def create_context(
        self,
        schedule_id: str,
        trace_id: Optional[str] = None,
        job_id: Optional[str] = None,
        **kwargs: Any,
    ) -> SchedulerContext:
        """Create a new scheduler execution context."""
        ctx = self._runtime_mgr.create_context(
            schedule_id=schedule_id, trace_id=trace_id, job_id=job_id, **kwargs,
        )
        with self._lock:
            self._contexts[ctx.execution_id] = ctx
        return ctx

    # ── internal: trigger evaluation ───────────────────────────────────────

    def _evaluate_triggers(self) -> List[JobDefinition]:
        """Evaluate all active schedules and create jobs for due ones."""
        if not self._registry:
            return []

        jobs: List[JobDefinition] = []
        now = datetime.now(timezone.utc)

        for schedule in self._registry.list_active():
            if not schedule.is_due(now):
                continue

            self._publish_event(
                SchedulerEventType.TRIGGER_EVALUATED,
                schedule.schedule_id,
                data={"due": True},
            )

            # Create job from trigger
            job = self._create_job_from_schedule(schedule)
            if job:
                self._metrics.triggers_total.inc()
                self._publish_event(
                    SchedulerEventType.JOB_CREATED,
                    schedule.schedule_id,
                    job_id=job.job_id,
                )
                jobs.append(job)

        return jobs

    def _create_job_from_schedule(self, schedule: ScheduleDefinition) -> Optional[JobDefinition]:
        """Create a job instance from a schedule trigger."""
        now = datetime.now(timezone.utc)
        job_id = f"job_{schedule.schedule_id}_{int(now.timestamp())}"

        job = JobDefinition(
            job_id=job_id,
            schedule_id=schedule.schedule_id,
            target=schedule.target,
            trigger_type=schedule.schedule_type.value,
            priority=JobDefinition.priority.field.default,  # type: ignore[attr-defined]
            payload=schedule.payload,
        )

        # Update schedule next_fire via registry
        if self._registry:
            try:
                updated = schedule.with_next_fire(now)
                self._registry._update(updated)
            except Exception:
                pass

        with self._lock:
            self._jobs[job.job_id] = job

        return job

    # ── internal: dispatch ─────────────────────────────────────────────────

    async def _dispatch_job(self, job: JobDefinition) -> None:
        """Dispatch a job to a worker."""
        self._metrics.dispatch_total.inc()
        self._metrics.queue_size.set(float(self._loop.queue_length))

        # Mark dispatched
        dispatched = job.transition_to(JobState.DISPATCHED)
        with self._lock:
            self._jobs[dispatched.job_id] = dispatched

        self._publish_event(
            SchedulerEventType.JOB_DISPATCHED,
            job.schedule_id,
            job_id=job.job_id,
        )

        # In practice, this would send to a worker via RPC/message queue.
        # For foundation, we simulate direct execution.
        ctx = self.create_context(
            schedule_id=job.schedule_id,
            job_id=job.job_id,
            trace_id=job.trace_id,
        )

        try:
            ctx.add_timeline_event("dispatched")
            # Simulate workflow execution (real impl would call workflow engine)
            await self._execute_job(dispatched, ctx)
        except Exception:
            logger.exception("SchedulerRuntime: job execution error %s", job.job_id)
            self._handle_job_failure(dispatched, "execution error")

    async def _execute_job(self, job: JobDefinition, ctx: SchedulerContext) -> None:
        """Execute a job and record results."""
        running = job.transition_to(JobState.RUNNING)
        with self._lock:
            self._jobs[running.job_id] = running

        self._publish_event(
            SchedulerEventType.JOB_STARTED,
            job.schedule_id,
            job_id=job.job_id,
        )
        self._metrics.active_jobs.inc()

        start = datetime.now(timezone.utc)

        # Simulate async execution (production: call workflow engine)
        await asyncio.sleep(0.01)

        duration = (datetime.now(timezone.utc) - start).total_seconds()
        self._metrics.job_duration.observe(duration)

        # Create execution record
        execution = ExecutionRecord(
            execution_id=f"exec_{job.job_id}",
            schedule_id=job.schedule_id,
            job_id=job.job_id,
            worker_id=ctx.worker_id,
            state=ExecutionState.COMPLETED,
            result=ExecutionResult.SUCCESS,
            payload=job.payload,
            started_at=start,
            completed_at=datetime.now(timezone.utc),
            duration_ms=duration * 1000,
            trace_id=ctx.trace_id,
        )

        completed = job.transition_to(JobState.COMPLETED)
        with self._lock:
            self._jobs[completed.job_id] = completed
            self._executions[execution.execution_id] = execution

        self._loop.complete_job(completed)
        self._metrics.active_jobs.dec()

        self._publish_event(
            SchedulerEventType.JOB_COMPLETED,
            job.schedule_id,
            job_id=job.job_id,
            execution_id=execution.execution_id,
            data=execution.to_dict(),
        )

    def _handle_job_failure(self, job: JobDefinition, error: str) -> None:
        """Handle a job failure."""
        failed = JobDefinition(
            job_id=job.job_id,
            schedule_id=job.schedule_id,
            target=job.target,
            trigger_type=job.trigger_type,
            priority=job.priority,
            state=JobState.FAILED,
            payload=job.payload,
            error_message=error,
            updated_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        with self._lock:
            self._jobs[failed.job_id] = failed

        self._metrics.errors_total.inc()
        self._publish_event(
            SchedulerEventType.JOB_FAILED,
            job.schedule_id,
            job_id=job.job_id,
            data={"error": error},
        )

    # ── events ─────────────────────────────────────────────────────────────

    def _publish_event(
        self,
        event_type: SchedulerEventType,
        schedule_id: str,
        job_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        """Publish a scheduler event to the event bus."""
        event = SchedulerEvent(
            event_type=event_type,
            schedule_id=schedule_id,
            data=data,
            job_id=job_id,
            execution_id=execution_id,
            trace_id=trace_id,
        )
        self._event_bus.publish(event)

    # ── observability ──────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def metrics(self) -> RuntimeMetricsCollector:
        return self._metrics

    def health_report(self) -> Dict[str, Any]:
        """Produce a health report."""
        return {
            "running": self._running,
            "paused": self._paused,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "active_jobs": len([j for j in self._jobs.values() if j.state not in (
                JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED,
            )]),
            "total_jobs": len(self._jobs),
            "runtime": self._runtime_mgr.health_report(),
            "metrics": self._metrics.health_report(),
            "loop": self._loop.health_report(),
        }
