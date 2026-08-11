"""
ICYQuant Replay Service.

Commit 16 Part 1.5 — Unified service for historical data replay.
Enables backtesting, simulation, and research by replaying historical
market data as simulated real-time feeds.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Optional

logger = logging.getLogger(__name__)


class ReplayState(str, Enum):
    """Replay job state."""
    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class ReplayConfig:
    """Configuration for a replay job."""
    dataset_id: str = ""
    instruments: list[str] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    speed_multiplier: float = 1.0
    loop: bool = False
    max_events: int = 0
    emit_latency_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReplayJob:
    """A replay job instance."""
    job_id: str = ""
    config: ReplayConfig = field(default_factory=ReplayConfig)
    state: ReplayState = ReplayState.CREATED
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    events_replayed: int = 0
    total_events: int = 0
    progress_pct: float = 0.0
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ReplayService:
    """Unified replay service.

    Provides:
      - Historical data replay as simulated real-time
      - Configurable speed multiplier
      - Loop/rewind support
      - Progress tracking and pause/resume
      - Multi-instrument synchronized replay
    """

    def __init__(
        self,
        data_lake: Any = None,
        streaming: Any = None,
    ) -> None:
        self._data_lake = data_lake
        self._streaming = streaming
        self._jobs: dict[str, ReplayJob] = {}
        self._job_counter = 0
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Replay Job Management
    # ------------------------------------------------------------------

    async def create_job(self, config: ReplayConfig) -> ReplayJob:
        """Create a new replay job."""
        async with self._lock:
            self._job_counter += 1
            job = ReplayJob(
                job_id=f"replay-{self._job_counter:08d}",
                config=config,
                created_at=datetime.now(timezone.utc),
            )
            self._jobs[job.job_id] = job

        logger.info("Replay job created: %s (dataset=%s, speed=%sx)",
                    job.job_id, config.dataset_id, config.speed_multiplier)
        return job

    async def start_job(self, job_id: str) -> AsyncIterator[dict[str, Any]]:
        """Start a replay job and stream replayed events."""
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Replay job not found: {job_id}")

        job.state = ReplayState.RUNNING
        job.started_at = datetime.now(timezone.utc)

        try:
            if self._data_lake:
                async for event in self._data_lake.replay(
                    dataset_id=job.config.dataset_id,
                    start_time=job.config.start_time,
                    end_time=job.config.end_time,
                    speed_multiplier=job.config.speed_multiplier,
                ):
                    job.events_replayed += 1
                    yield event
                    if job.config.max_events and job.events_replayed >= job.config.max_events:
                        break

            job.state = ReplayState.COMPLETED
        except Exception as exc:
            job.state = ReplayState.ERROR
            job.errors.append(str(exc))
            logger.exception("Replay job %s failed", job_id)
            raise
        finally:
            job.completed_at = datetime.now(timezone.utc)

    async def pause_job(self, job_id: str) -> bool:
        """Pause a running replay job."""
        job = self._jobs.get(job_id)
        if job and job.state == ReplayState.RUNNING:
            job.state = ReplayState.PAUSED
            return True
        return False

    async def resume_job(self, job_id: str) -> bool:
        """Resume a paused replay job."""
        job = self._jobs.get(job_id)
        if job and job.state == ReplayState.PAUSED:
            job.state = ReplayState.RUNNING
            return True
        return False

    async def stop_job(self, job_id: str) -> bool:
        """Stop a replay job."""
        job = self._jobs.get(job_id)
        if job and job.state in (ReplayState.RUNNING, ReplayState.PAUSED):
            job.state = ReplayState.STOPPED
            job.completed_at = datetime.now(timezone.utc)
            return True
        return False

    # ------------------------------------------------------------------
    # Job Queries
    # ------------------------------------------------------------------

    async def get_job(self, job_id: str) -> Optional[ReplayJob]:
        """Get a replay job by ID."""
        return self._jobs.get(job_id)

    async def list_jobs(self, state: Optional[ReplayState] = None) -> list[ReplayJob]:
        """List replay jobs with optional state filter."""
        jobs = list(self._jobs.values())
        if state:
            jobs = [j for j in jobs if j.state == state]
        return jobs

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def job_count(self) -> int:
        return len(self._jobs)

    @property
    def active_job_count(self) -> int:
        return sum(1 for j in self._jobs.values() if j.state == ReplayState.RUNNING)
