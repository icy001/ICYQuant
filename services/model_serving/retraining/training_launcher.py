"""
ICYQuant Training Launcher — Launches ML training for retraining workflow.

Orchestrates:
  - Training pipeline invocation
  - Hyperparameter configuration
  - Resource allocation
  - Training progress tracking
  - Artifact registration
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class TrainingStatus(str, Enum):
    """Training job status."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TrainingConfig:
    """Training configuration."""
    model_id: str
    model_type: str = "lightgbm"  # lightgbm, xgboost, catboost, pytorch
    hyperparameters: Dict[str, Any] = field(default_factory=dict)
    cross_validation_folds: int = 5
    early_stopping_rounds: int = 50
    validation_split: float = 0.2
    random_seed: int = 42
    timeout_seconds: int = 3600
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrainingJob:
    """A training job instance."""
    job_id: str
    model_id: str
    status: TrainingStatus = TrainingStatus.QUEUED
    candidate_version: Optional[str] = None
    config: Optional[TrainingConfig] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Training Launcher
# ---------------------------------------------------------------------------

class TrainingLauncher:
    """Launches and manages training jobs for retraining.

    Usage::

        launcher = TrainingLauncher()
        job = await launcher.launch_training(config)
        result = await launcher.wait_for_completion(job.job_id)
    """

    def __init__(self):
        self._initialized = False
        self._jobs: Dict[str, TrainingJob] = {}
        self._active_jobs: Dict[str, asyncio.Task] = {}
        self._max_concurrent_trainings: int = 2

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("TrainingLauncher initialized")

    # ------------------------------------------------------------------
    # Launch
    # ------------------------------------------------------------------

    async def launch_training(
        self,
        config: TrainingConfig,
    ) -> TrainingJob:
        """Launch a training job.

        Args:
            config: Training configuration.

        Returns:
            TrainingJob with job ID for tracking.
        """
        job_id = str(uuid.uuid4())
        candidate_version = f"candidate_{job_id[:8]}"

        job = TrainingJob(
            job_id=job_id,
            model_id=config.model_id,
            status=TrainingStatus.QUEUED,
            candidate_version=candidate_version,
            config=config,
        )

        self._jobs[job_id] = job

        # Start training asynchronously
        task = asyncio.create_task(self._run_training(job))
        self._active_jobs[job_id] = task

        logger.info(
            "Training launched: %s for %s (candidate=%s)",
            job_id[:8], config.model_id, candidate_version,
        )

        return job

    async def _run_training(self, job: TrainingJob) -> None:
        """Execute the training pipeline."""
        job.status = TrainingStatus.RUNNING
        job.started_at = datetime.now(timezone.utc).isoformat()

        try:
            # Placeholder — actual training would invoke ML pipeline
            await asyncio.sleep(0.2)

            job.metrics = {
                "ic": 0.071,
                "rank_ic": 0.094,
                "sharpe": 1.82,
                "max_drawdown": -0.087,
                "accuracy": 0.54,
                "training_duration_seconds": 180.0,
            }

            job.status = TrainingStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc).isoformat()

            logger.info(
                "Training completed: %s/%s (ic=%.4f)",
                job.model_id, job.candidate_version,
                job.metrics.get("ic", 0),
            )

        except Exception as exc:
            job.status = TrainingStatus.FAILED
            job.error = str(exc)
            job.completed_at = datetime.now(timezone.utc).isoformat()
            logger.error("Training failed: %s/%s", job.model_id, job.job_id[:8])

        finally:
            self._active_jobs.pop(job.job_id, None)

    # ------------------------------------------------------------------
    # Retrain with existing config
    # ------------------------------------------------------------------

    async def retrain_from_production(
        self,
        model_id: str,
        previous_hyperparams: Optional[Dict[str, Any]] = None,
    ) -> TrainingJob:
        """Retrain using production model's original configuration."""
        config = TrainingConfig(
            model_id=model_id,
            hyperparameters=previous_hyperparams or {},
        )
        return await self.launch_training(config)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def get_job(self, job_id: str) -> Optional[TrainingJob]:
        return self._jobs.get(job_id)

    async def wait_for_completion(
        self,
        job_id: str,
        timeout_seconds: Optional[float] = None,
    ) -> TrainingJob:
        """Wait for a training job to complete."""
        job = self._jobs.get(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")

        if job.status in (TrainingStatus.COMPLETED, TrainingStatus.FAILED):
            return job

        task = self._active_jobs.get(job_id)
        if task:
            try:
                await asyncio.wait_for(task, timeout=timeout_seconds)
            except asyncio.TimeoutError:
                job.status = TrainingStatus.CANCELLED
                job.error = "Timeout waiting for training"
            return self._jobs[job_id]

        return job

    def list_jobs(self, model_id: Optional[str] = None) -> List[Dict[str, Any]]:
        jobs = self._jobs.values()
        if model_id:
            jobs = [j for j in jobs if j.model_id == model_id]
        return [
            {
                "job_id": j.job_id[:8],
                "model_id": j.model_id,
                "status": j.status.value,
                "candidate_version": j.candidate_version,
                "created_at": j.created_at,
            }
            for j in jobs
        ]

    def cancel_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job and job.status == TrainingStatus.RUNNING:
            job.status = TrainingStatus.CANCELLED
            task = self._active_jobs.pop(job_id, None)
            if task:
                task.cancel()
            return True
        return False

    async def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "active_trainings": len(self._active_jobs),
            "total_jobs": len(self._jobs),
        }

    def __repr__(self) -> str:
        return f"TrainingLauncher(jobs={len(self._jobs)}, active={len(self._active_jobs)})"
