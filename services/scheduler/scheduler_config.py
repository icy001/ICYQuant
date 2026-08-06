"""Scheduler Config — configuration management for the distributed scheduler."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SchedulerConfig:
    """Configuration for the distributed scheduler engine.

    Controls all runtime behavior including timing, resource limits,
    concurrency, and retry policies.

    Usage::

        config = SchedulerConfig(
            tick_interval=0.1,
            max_queue_size=10000,
            max_concurrent_jobs=100,
        )
    """

    # Core timing
    tick_interval: float = 0.1  # seconds between scheduler loop ticks
    trigger_evaluation_interval: float = 1.0  # seconds between trigger evaluations

    # Queue
    max_queue_size: int = 10000
    queue_drain_batch: int = 50

    # Concurrency
    max_concurrent_jobs: int = 100
    max_concurrent_per_schedule: int = 10
    max_concurrent_per_worker: int = 20

    # Timeouts
    job_timeout_seconds: float = 3600.0  # 1 hour default
    dispatch_timeout_seconds: float = 30.0
    trigger_timeout_seconds: float = 5.0

    # Retry
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    retry_backoff_multiplier: float = 2.0

    # Misfire
    misfire_policy: str = "ignore"  # ignore | fire_once | fire_all
    misfire_threshold_seconds: float = 60.0

    # Overlap
    overlapping_policy: str = "skip"  # skip | allow | queue

    # Persistence
    persist_jobs: bool = True
    persist_executions: bool = True
    snapshot_interval_seconds: float = 60.0

    # Telemetry
    telemetry_enabled: bool = True
    metrics_enabled: bool = True
    tracing_enabled: bool = True

    # Labels / tags / metadata
    labels: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "tick_interval": self.tick_interval,
            "trigger_evaluation_interval": self.trigger_evaluation_interval,
            "max_queue_size": self.max_queue_size,
            "queue_drain_batch": self.queue_drain_batch,
            "max_concurrent_jobs": self.max_concurrent_jobs,
            "max_concurrent_per_schedule": self.max_concurrent_per_schedule,
            "max_concurrent_per_worker": self.max_concurrent_per_worker,
            "job_timeout_seconds": self.job_timeout_seconds,
            "dispatch_timeout_seconds": self.dispatch_timeout_seconds,
            "trigger_timeout_seconds": self.trigger_timeout_seconds,
            "max_retries": self.max_retries,
            "retry_delay_seconds": self.retry_delay_seconds,
            "retry_backoff_multiplier": self.retry_backoff_multiplier,
            "misfire_policy": self.misfire_policy,
            "misfire_threshold_seconds": self.misfire_threshold_seconds,
            "overlapping_policy": self.overlapping_policy,
            "persist_jobs": self.persist_jobs,
            "persist_executions": self.persist_executions,
            "snapshot_interval_seconds": self.snapshot_interval_seconds,
            "telemetry_enabled": self.telemetry_enabled,
            "metrics_enabled": self.metrics_enabled,
            "tracing_enabled": self.tracing_enabled,
            "labels": self.labels,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SchedulerConfig:
        """Create from dictionary."""
        field_names = {f.name for f in cls.__dataclass_fields__.values()}
        kwargs = {k: v for k, v in data.items() if k in field_names}
        return cls(**kwargs)
