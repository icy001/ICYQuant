"""Scheduler Metrics — Prometheus-compatible metrics for the distributed scheduler.

Exports metrics for:
* Job throughput and latency
* Trigger evaluation and misfire rates
* Dispatch queue depth and wait times
* Snapshot operations
"""

from __future__ import annotations

import threading
from typing import Any, Dict

from .runtime.runtime_metrics import (
    RuntimeMetricsCollector,
    _Counter,
    _Gauge,
    _Histogram,
)


class SchedulerMetrics:
    """Top-level metrics collector for the scheduler engine.

    Aggregates runtime metrics and adds engine-level counters
    for schedule lifecycle operations.

    Usage::

        metrics = SchedulerMetrics()
        metrics.schedules_registered.inc()
        metrics.job_duration.observe(2.5)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

        # Counters — schedule lifecycle
        self.schedules_registered = _Counter(
            "icyquant_scheduler_schedules_registered_total",
            "Total number of schedules registered",
        )
        self.schedules_removed = _Counter(
            "icyquant_scheduler_schedules_removed_total",
            "Total number of schedules removed",
        )
        self.schedules_paused = _Counter(
            "icyquant_scheduler_schedules_paused_total",
            "Total number of schedules paused",
        )
        self.schedules_resumed = _Counter(
            "icyquant_scheduler_schedules_resumed_total",
            "Total number of schedules resumed",
        )

        # Counters — trigger
        self.triggers_total = _Counter(
            "icyquant_scheduler_trigger_evaluations_total",
            "Total number of trigger evaluations",
        )
        self.misfires_total = _Counter(
            "icyquant_scheduler_misfires_total",
            "Total number of misfired triggers",
        )

        # Counters — jobs
        self.jobs_total = _Counter(
            "icyquant_scheduler_jobs_total",
            "Total number of jobs processed",
        )
        self.jobs_created = _Counter(
            "icyquant_scheduler_jobs_created_total",
            "Total number of jobs created",
        )
        self.jobs_dispatched = _Counter(
            "icyquant_scheduler_jobs_dispatched_total",
            "Total number of jobs dispatched",
        )
        self.jobs_completed = _Counter(
            "icyquant_scheduler_jobs_completed_total",
            "Total number of jobs completed",
        )
        self.jobs_failed = _Counter(
            "icyquant_scheduler_jobs_failed_total",
            "Total number of jobs failed",
        )

        # Counters — snapshots / operations
        self.snapshots_total = _Counter(
            "icyquant_scheduler_snapshot_total",
            "Total number of snapshots taken",
        )
        self.errors_total = _Counter(
            "icyquant_scheduler_errors_total",
            "Total number of scheduler errors",
        )

        # Gauges
        self.queue_size = _Gauge(
            "icyquant_scheduler_queue_size",
            "Current number of queued jobs",
        )
        self.active_jobs = _Gauge(
            "icyquant_scheduler_active_jobs",
            "Current number of active jobs",
        )
        self.active_schedules = _Gauge(
            "icyquant_scheduler_active_schedules",
            "Current number of active schedules",
        )
        self.schedules_total = _Gauge(
            "icyquant_scheduler_schedules_total",
            "Current number of registered schedules",
        )

        # Histograms
        self.job_duration = _Histogram(
            "icyquant_scheduler_job_duration_seconds",
            "Job execution duration histogram",
        )
        self.job_wait_time = _Histogram(
            "icyquant_scheduler_job_wait_seconds",
            "Time a job spends waiting in the queue",
        )
        self.trigger_evaluation = _Histogram(
            "icyquant_scheduler_trigger_evaluation_seconds",
            "Trigger evaluation time histogram",
        )
        self.dispatch_latency = _Histogram(
            "icyquant_scheduler_dispatch_latency_seconds",
            "Job dispatch latency histogram",
        )
        self.snapshot_duration = _Histogram(
            "icyquant_scheduler_snapshot_duration_seconds",
            "Snapshot operation duration",
        )

    def record_schedule_registered(self) -> None:
        """Record a schedule registration event."""
        self.schedules_registered.inc()
        self.schedules_total.inc()

    def record_schedule_removed(self) -> None:
        """Record a schedule removal event."""
        self.schedules_removed.inc()
        self.schedules_total.dec()

    def record_schedule_paused(self) -> None:
        """Record a schedule pause event."""
        self.schedules_paused.inc()
        self.active_schedules.dec()

    def record_schedule_resumed(self) -> None:
        """Record a schedule resume event."""
        self.schedules_resumed.inc()
        self.active_schedules.inc()

    def record_trigger_evaluation(self, duration_seconds: float) -> None:
        """Record a trigger evaluation with duration."""
        self.triggers_total.inc()
        self.trigger_evaluation.observe(duration_seconds)

    def record_misfire(self) -> None:
        """Record a trigger misfire."""
        self.misfires_total.inc()

    def record_job_created(self) -> None:
        """Record a job creation."""
        self.jobs_created.inc()
        self.jobs_total.inc()

    def record_job_dispatched(self, wait_seconds: float) -> None:
        """Record a job dispatch with wait time."""
        self.jobs_dispatched.inc()
        self.job_wait_time.observe(wait_seconds)
        self.queue_size.dec()

    def record_job_completed(self, duration_seconds: float) -> None:
        """Record a job completion with duration."""
        self.jobs_completed.inc()
        self.job_duration.observe(duration_seconds)
        self.active_jobs.dec()

    def record_job_failed(self) -> None:
        """Record a job failure."""
        self.jobs_failed.inc()
        self.active_jobs.dec()

    def record_error(self) -> None:
        """Record a scheduler error."""
        self.errors_total.inc()

    def snapshot(self) -> Dict[str, Any]:
        """Return a snapshot of all current metrics."""
        result: Dict[str, Any] = {}
        for attr_name in dir(self):
            if attr_name.startswith("_"):
                continue
            attr = getattr(self, attr_name, None)
            if isinstance(attr, _Counter):
                result[attr.name] = {"type": "counter", "value": attr.value}
            elif isinstance(attr, _Gauge):
                result[attr.name] = {"type": "gauge", "value": attr.value}
            elif isinstance(attr, _Histogram):
                result[attr.name] = {
                    "type": "histogram",
                    "sum": attr.sum,
                    "count": attr.count,
                }
        return result

    def health_report(self) -> Dict[str, Any]:
        """Produce a health report for metrics."""
        return {"metrics_snapshot": self.snapshot()}
