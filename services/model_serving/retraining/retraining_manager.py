"""
ICYQuant Retraining Manager — Orchestrates automated model retraining.

Coordinates the full retraining lifecycle:
  Trigger → Dataset Refresh → Training → Validation → Comparison → Promotion

Integrates with monitoring, drift detection, and deployment systems
to close the ML feedback loop automatically.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .retraining_trigger import RetrainingTrigger
    from .retraining_scheduler import RetrainingScheduler
    from .retraining_policy import RetrainingPolicy
    from .dataset_refresh import DatasetRefresher
    from .training_launcher import TrainingLauncher
    from .candidate_validator import CandidateValidator
    from .model_comparator import ModelComparator
    from .promotion_manager import PromotionManager

logger = logging.getLogger(__name__)

import asyncio
import uuid


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RetrainingStatus(str, Enum):
    """Retraining run lifecycle."""
    PENDING = "pending"
    TRIGGERED = "triggered"
    REFRESHING_DATA = "refreshing_data"
    TRAINING = "training"
    VALIDATING = "validating"
    COMPARING = "comparing"
    PROMOTING = "promoting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TriggerReason(str, Enum):
    """Why retraining was triggered."""
    SCHEDULED = "scheduled"
    DRIFT_DETECTED = "drift_detected"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    DATA_QUALITY = "data_quality"
    MANUAL = "manual"
    ON_NEW_DATA = "on_new_data"
    PRE_DEPLOYMENT = "pre_deployment"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class RetrainingRun:
    """A single retraining execution."""
    run_id: str
    model_id: str
    trigger_reason: TriggerReason
    status: RetrainingStatus = RetrainingStatus.PENDING
    candidate_version: Optional[str] = None
    production_version: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)

    def record_step(self, step: str, detail: Optional[Dict[str, Any]] = None) -> None:
        self.history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "step": step,
            "status": self.status.value,
            "detail": detail or {},
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "model_id": self.model_id,
            "trigger_reason": self.trigger_reason.value,
            "status": self.status.value,
            "candidate_version": self.candidate_version,
            "production_version": self.production_version,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "metrics": self.metrics,
        }


# ---------------------------------------------------------------------------
# Retraining Manager
# ---------------------------------------------------------------------------

class RetrainingManager:
    """Central retraining orchestrator.

    Pipeline:
      1. Receive trigger (drift, schedule, manual, performance)
      2. Refresh training dataset with latest data
      3. Launch training pipeline
      4. Validate candidate model
      5. Compare with production
      6. Decide promotion

    Usage::

        manager = RetrainingManager()
        await manager.initialize()
        run_id = await manager.trigger("nvda_model", reason=TriggerReason.DRIFT_DETECTED)
        status = await manager.get_status(run_id)
    """

    def __init__(self):
        self._initialized = False

        # Active and completed runs
        self._runs: Dict[str, RetrainingRun] = {}
        self._active_runs: Dict[str, RetrainingRun] = {}

        # Concurrency control
        self._run_lock = asyncio.Lock()
        self._max_concurrent_runs: int = 3

        # Subsystems (lazy)
        self._trigger: Optional[RetrainingTrigger] = None
        self._scheduler: Optional[RetrainingScheduler] = None
        self._refresher: Optional[DatasetRefresher] = None
        self._launcher: Optional[TrainingLauncher] = None
        self._validator: Optional[CandidateValidator] = None
        self._comparator: Optional[ModelComparator] = None
        self._promotion: Optional[PromotionManager] = None

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("RetrainingManager initialized")

    # ------------------------------------------------------------------
    # Trigger
    # ------------------------------------------------------------------

    async def trigger(
        self,
        model_id: str,
        reason: TriggerReason = TriggerReason.MANUAL,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Trigger a retraining run.

        Args:
            model_id: Model to retrain.
            reason: Why retraining was triggered.
            metadata: Additional context.

        Returns:
            Run ID for tracking.
        """
        async with self._run_lock:
            # Check if already retraining this model
            for run in self._active_runs.values():
                if run.model_id == model_id:
                    logger.warning(
                        "Retraining already in progress for %s (run=%s)",
                        model_id, run.run_id,
                    )
                    return run.run_id

            # Check concurrent limit
            if len(self._active_runs) >= self._max_concurrent_runs:
                raise RuntimeError(
                    f"Max concurrent retraining runs ({self._max_concurrent_runs}) reached"
                )

            run_id = str(uuid.uuid4())
            run = RetrainingRun(
                run_id=run_id,
                model_id=model_id,
                trigger_reason=reason,
                status=RetrainingStatus.TRIGGERED,
                metadata=metadata or {},
            )

            self._runs[run_id] = run
            self._active_runs[run_id] = run

        logger.info(
            "Retraining triggered: %s for %s (reason=%s)",
            run_id, model_id, reason.value,
        )

        # Execute pipeline asynchronously
        asyncio.create_task(self._execute_pipeline(run))

        return run_id

    async def cancel(self, run_id: str) -> bool:
        """Cancel a running retraining pipeline."""
        run = self._runs.get(run_id)
        if run is None:
            return False

        if run.status in (
            RetrainingStatus.COMPLETED,
            RetrainingStatus.FAILED,
            RetrainingStatus.CANCELLED,
        ):
            return False

        run.status = RetrainingStatus.CANCELLED
        run.completed_at = datetime.now(timezone.utc).isoformat()
        self._active_runs.pop(run_id, None)
        return True

    # ------------------------------------------------------------------
    # Pipeline execution
    # ------------------------------------------------------------------

    async def _execute_pipeline(self, run: RetrainingRun) -> None:
        """Execute the full retraining pipeline."""
        run.started_at = datetime.now(timezone.utc).isoformat()

        try:
            # Step 1: Refresh dataset
            run.status = RetrainingStatus.REFRESHING_DATA
            run.record_step("refreshing_data")
            logger.info("[%s] Refreshing dataset...", run.run_id[:8])
            await asyncio.sleep(0.1)  # Placeholder — actual dataset refresh

            # Step 2: Launch training
            run.status = RetrainingStatus.TRAINING
            run.record_step("training_started")
            logger.info("[%s] Training model...", run.run_id[:8])
            # Placeholder — actual training happens here via ML pipeline
            candidate_version = f"retrain_{run.run_id[:8]}"
            run.candidate_version = candidate_version
            await asyncio.sleep(0.1)

            # Step 3: Validate candidate
            run.status = RetrainingStatus.VALIDATING
            run.record_step("validating")
            logger.info("[%s] Validating candidate %s...", run.run_id[:8], candidate_version)
            await asyncio.sleep(0.1)

            # Step 4: Compare with production
            run.status = RetrainingStatus.COMPARING
            run.record_step("comparing")
            logger.info("[%s] Comparing with production...", run.run_id[:8])
            await asyncio.sleep(0.1)

            # Step 5: Decide promotion
            run.status = RetrainingStatus.PROMOTING
            run.record_step("promotion_decision")
            logger.info("[%s] Promotion decision pending...", run.run_id[:8])

            # Complete
            run.status = RetrainingStatus.COMPLETED
            run.completed_at = datetime.now(timezone.utc).isoformat()
            run.record_step("completed")

            logger.info(
                "[%s] Retraining completed: %s → candidate=%s",
                run.run_id[:8], run.model_id, run.candidate_version,
            )

        except Exception as exc:
            run.status = RetrainingStatus.FAILED
            run.error = str(exc)
            run.completed_at = datetime.now(timezone.utc).isoformat()
            run.record_step("failed", {"error": str(exc)})
            logger.exception("[%s] Retraining failed: %s", run.run_id[:8], exc)

        finally:
            self._active_runs.pop(run.run_id, None)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def get_status(self, run_id: str) -> Dict[str, Any]:
        """Get retraining run status."""
        run = self._runs.get(run_id)
        if run is None:
            return {"error": "not_found"}
        return run.to_dict()

    def list_runs(self, model_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List retraining runs, optionally filtered by model."""
        runs = self._runs.values()
        if model_id:
            runs = [r for r in runs if r.model_id == model_id]
        return [r.to_dict() for r in runs]

    def get_active_runs(self) -> List[Dict[str, Any]]:
        """Get currently active runs."""
        return [r.to_dict() for r in self._active_runs.values()]

    async def compare_versions(
        self,
        model_id: str,
        version_a: str,
        version_b: str,
    ) -> Dict[str, Any]:
        """Compare two model versions (placeholder)."""
        return {
            "model_id": model_id,
            "version_a": version_a,
            "version_b": version_b,
            "metrics": {},
            "recommendation": "comparison_pending",
        }

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        active_count = len(self._active_runs)
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "active_runs": active_count,
            "total_runs": len(self._runs),
            "max_concurrent": self._max_concurrent_runs,
        }

    def __repr__(self) -> str:
        return (
            f"RetrainingManager(active={len(self._active_runs)}, "
            f"total={len(self._runs)})"
        )
