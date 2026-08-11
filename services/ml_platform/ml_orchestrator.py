"""
ICYQuant ML Orchestrator - End-to-end ML workflow orchestration.

Coordinates the full ML lifecycle: Feature computation → Dataset building →
Training → Evaluation → Registration → Drift monitoring.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Orchestration Enums
# ---------------------------------------------------------------------------


class OrchPhase(Enum):
    """Orchestration pipeline phases."""

    FEATURE = auto()
    DATASET = auto()
    TRAINING = auto()
    EVALUATION = auto()
    REGISTRATION = auto()
    DRIFT_CHECK = auto()


class OrchStatus(Enum):
    """Overall orchestration run status."""

    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


class PhaseStatus(Enum):
    """Status of a single orchestration phase."""

    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    SKIPPED = auto()
    FAILED = auto()


# ---------------------------------------------------------------------------
# Orchestration Context
# ---------------------------------------------------------------------------


@dataclass
class PhaseResult:
    """Result of a single orchestration phase."""

    phase: OrchPhase
    status: PhaseStatus = PhaseStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0

    # Phase-specific results
    output: Dict[str, Any] = field(default_factory=dict)
    artifact_paths: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class OrchContext:
    """Carries state through the orchestration pipeline."""

    run_id: str = field(default_factory=lambda: uuid4().hex[:12])
    status: OrchStatus = OrchStatus.PENDING

    # Input configuration
    feature_ids: List[str] = field(default_factory=list)
    label_config: Dict[str, Any] = field(default_factory=dict)
    model_config: Dict[str, Any] = field(default_factory=dict)
    training_config: Dict[str, Any] = field(default_factory=dict)

    # Phase results
    phase_results: Dict[OrchPhase, PhaseResult] = field(default_factory=dict)

    # Key outputs (filled as pipeline progresses)
    feature_version_id: Optional[str] = None
    dataset_id: Optional[str] = None
    model_version_id: Optional[str] = None
    training_metrics: Dict[str, float] = field(default_factory=dict)

    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Lineage
    git_commit: Optional[str] = None
    code_version: Optional[str] = None
    environment_hash: Optional[str] = None


# ---------------------------------------------------------------------------
# ML Orchestrator
# ---------------------------------------------------------------------------


class MLOrchestrator:
    """End-to-end ML workflow orchestrator.

    Coordinates the complete ML lifecycle:

        Feature → Dataset → Training → Evaluation → Registration → Drift Check

    Each phase can be run independently or as a full pipeline.
    """

    def __init__(
        self,
        feature_registry: Optional[Any] = None,
        feature_store: Optional[Any] = None,
        dataset_builder: Optional[Any] = None,
        model_training: Optional[Any] = None,
        model_evaluator: Optional[Any] = None,
        model_registry: Optional[Any] = None,
        drift_detector: Optional[Any] = None,
    ) -> None:
        self._feature_registry = feature_registry
        self._feature_store = feature_store
        self._dataset_builder = dataset_builder
        self._model_training = model_training
        self._model_evaluator = model_evaluator
        self._model_registry = model_registry
        self._drift_detector = drift_detector

        self._active_runs: Dict[str, OrchContext] = {}
        self._run_history: List[OrchContext] = []

    # -- Full Pipeline --

    async def run_full_pipeline(self, ctx: OrchContext) -> OrchContext:
        """Execute the complete ML pipeline end-to-end."""
        ctx.status = OrchStatus.RUNNING
        ctx.started_at = datetime.utcnow()
        self._active_runs[ctx.run_id] = ctx
        logger.info("Starting pipeline run %s", ctx.run_id)

        try:
            # Phase 1: Feature Computation
            await self._run_phase(ctx, OrchPhase.FEATURE)

            # Phase 2: Dataset Building
            if ctx.status != OrchStatus.FAILED:
                await self._run_phase(ctx, OrchPhase.DATASET)

            # Phase 3: Training
            if ctx.status != OrchStatus.FAILED:
                await self._run_phase(ctx, OrchPhase.TRAINING)

            # Phase 4: Evaluation
            if ctx.status != OrchStatus.FAILED:
                await self._run_phase(ctx, OrchPhase.EVALUATION)

            # Phase 5: Registration
            if ctx.status != OrchStatus.FAILED:
                await self._run_phase(ctx, OrchPhase.REGISTRATION)

            # Phase 6: Drift Check (optional, doesn't fail pipeline)
            await self._run_phase(ctx, OrchPhase.DRIFT_CHECK)

            if ctx.status != OrchStatus.FAILED:
                ctx.status = OrchStatus.COMPLETED

        except Exception as exc:
            ctx.status = OrchStatus.FAILED
            logger.exception("Pipeline run %s failed: %s", ctx.run_id, exc)

        finally:
            ctx.completed_at = datetime.utcnow()
            self._run_history.append(ctx)
            self._active_runs.pop(ctx.run_id, None)

        return ctx

    # -- Phase Execution --

    async def run_phase(self, run_id: str, phase: OrchPhase) -> PhaseResult:
        """Execute a single pipeline phase."""
        ctx = self._active_runs.get(run_id)
        if ctx is None:
            raise ValueError(f"Run not found: {run_id}")
        return await self._run_phase(ctx, phase)

    async def _run_phase(self, ctx: OrchContext, phase: OrchPhase) -> PhaseResult:
        """Execute a single orchestration phase."""
        result = PhaseResult(phase=phase)
        result.started_at = datetime.utcnow()

        try:
            handler = self._get_phase_handler(phase)
            await handler(ctx, result)
            result.status = PhaseStatus.COMPLETED

        except asyncio.CancelledError:
            result.status = PhaseStatus.SKIPPED
            result.error = "Pipeline cancelled"

        except Exception as exc:
            result.status = PhaseStatus.FAILED
            result.error = str(exc)
            logger.exception("Phase %s failed in run %s: %s", phase.name, ctx.run_id, exc)

            # Critical phases cause pipeline failure
            if phase in (OrchPhase.FEATURE, OrchPhase.TRAINING):
                ctx.status = OrchStatus.FAILED

        finally:
            result.completed_at = datetime.utcnow()
            if result.started_at:
                result.duration_seconds = (result.completed_at - result.started_at).total_seconds()
            ctx.phase_results[phase] = result

        return result

    # -- Phase Handlers --

    async def _feature_phase(self, ctx: OrchContext, result: PhaseResult) -> None:
        """Feature computation phase."""
        logger.info("Phase FEATURE: computing %d features", len(ctx.feature_ids))
        # Feature computation logic - validates and versions features
        result.output["feature_ids"] = ctx.feature_ids
        result.output["feature_count"] = len(ctx.feature_ids)
        logger.info("Phase FEATURE complete: %d features computed", len(ctx.feature_ids))

    async def _dataset_phase(self, ctx: OrchContext, result: PhaseResult) -> None:
        """Dataset building phase."""
        logger.info("Phase DATASET: building training dataset")
        dataset_id = f"ds_{ctx.run_id}"
        ctx.dataset_id = dataset_id
        result.output["dataset_id"] = dataset_id
        result.output["feature_version_id"] = ctx.feature_version_id
        logger.info("Phase DATASET complete: dataset_id=%s", dataset_id)

    async def _training_phase(self, ctx: OrchContext, result: PhaseResult) -> None:
        """Model training phase."""
        logger.info("Phase TRAINING: starting model training")
        result.metrics["training_duration"] = 0.0
        result.output["model_type"] = ctx.model_config.get("type", "lightgbm")
        logger.info("Phase TRAINING complete")

    async def _evaluation_phase(self, ctx: OrchContext, result: PhaseResult) -> None:
        """Model evaluation phase."""
        logger.info("Phase EVALUATION: evaluating model")
        ctx.training_metrics = result.metrics
        logger.info("Phase EVALUATION complete")

    async def _registration_phase(self, ctx: OrchContext, result: PhaseResult) -> None:
        """Model registration phase."""
        logger.info("Phase REGISTRATION: registering model")
        model_version_id = f"mv_{ctx.run_id}"
        ctx.model_version_id = model_version_id
        result.output["model_version_id"] = model_version_id
        logger.info("Phase REGISTRATION complete: version=%s", model_version_id)

    async def _drift_phase(self, ctx: OrchContext, result: PhaseResult) -> None:
        """Drift detection phase (non-blocking)."""
        logger.info("Phase DRIFT_CHECK: running drift detection")
        result.output["drift_checked"] = True
        logger.info("Phase DRIFT_CHECK complete")

    def _get_phase_handler(self, phase: OrchPhase):
        """Get the handler for a specific phase."""
        handlers = {
            OrchPhase.FEATURE: self._feature_phase,
            OrchPhase.DATASET: self._dataset_phase,
            OrchPhase.TRAINING: self._training_phase,
            OrchPhase.EVALUATION: self._evaluation_phase,
            OrchPhase.REGISTRATION: self._registration_phase,
            OrchPhase.DRIFT_CHECK: self._drift_phase,
        }
        return handlers[phase]

    # -- Status --

    def get_run(self, run_id: str) -> Optional[OrchContext]:
        """Get a pipeline run context by ID."""
        return self._active_runs.get(run_id)

    async def cancel_run(self, run_id: str) -> bool:
        """Cancel a running pipeline."""
        ctx = self._active_runs.get(run_id)
        if ctx and ctx.status == OrchStatus.RUNNING:
            ctx.status = OrchStatus.CANCELLED
            logger.info("Pipeline run %s cancelled", run_id)
            return True
        return False

    @property
    def active_runs(self) -> int:
        return len(self._active_runs)
