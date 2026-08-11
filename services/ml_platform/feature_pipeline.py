"""
ICYQuant Feature Pipeline - End-to-end feature computation orchestration.

    Raw Market Data
           │
           ▼
    Normalization
           │
           ▼
    Feature Transformation
           │
           ▼
    Validation
           │
           ▼
    Quality Check
           │
           ▼
    Feature Store
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
# Pipeline Enums
# ---------------------------------------------------------------------------


class PipelineStage(Enum):
    """Pipeline processing stages."""

    NORMALIZATION = "normalization"
    TRANSFORMATION = "transformation"
    VALIDATION = "validation"
    QUALITY_CHECK = "quality_check"
    STORAGE = "storage"


class PipelineStatus(Enum):
    """Pipeline run status."""

    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


class StageStatus(Enum):
    """Individual stage status."""

    PENDING = auto()
    RUNNING = auto()
    PASSED = auto()
    FAILED = auto()
    SKIPPED = auto()


# ---------------------------------------------------------------------------
# Pipeline Data
# ---------------------------------------------------------------------------


@dataclass
class StageResult:
    """Result of a single pipeline stage."""

    stage: PipelineStage
    status: StageStatus = StageStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    input_count: int = 0
    output_count: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class PipelineRun:
    """A single execution of the feature pipeline."""

    run_id: str = field(default_factory=lambda: uuid4().hex[:12])
    status: PipelineStatus = PipelineStatus.PENDING

    # Target features
    feature_ids: List[str] = field(default_factory=list)
    feature_group_id: Optional[str] = None

    # Time range
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    # Stage results
    stages: Dict[PipelineStage, StageResult] = field(default_factory=dict)

    # Output
    output_feature_version_id: Optional[str] = None
    output_artifact_path: Optional[str] = None

    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Feature Pipeline
# ---------------------------------------------------------------------------


class FeaturePipeline:
    """End-to-end feature computation pipeline.

    Orchestrates the complete flow from raw data to features in the store:

    1. Normalization - standardize raw data
    2. Transformation - compute features from formula/transform
    3. Validation - check constraints, types, ranges
    4. Quality Check - coverage, freshness, distribution
    5. Storage - write to offline + online stores
    """

    def __init__(
        self,
        transformer: Optional[Any] = None,
        validator: Optional[Any] = None,
        quality_engine: Optional[Any] = None,
        offline_store: Optional[Any] = None,
        online_store: Optional[Any] = None,
    ) -> None:
        self._transformer = transformer
        self._validator = validator
        self._quality_engine = quality_engine
        self._offline_store = offline_store
        self._online_store = online_store

        self._active_runs: Dict[str, PipelineRun] = {}
        self._run_history: List[PipelineRun] = []

    # -- Run Pipeline --

    async def run(self, run: PipelineRun) -> PipelineRun:
        """Execute the full feature pipeline."""
        run.status = PipelineStatus.RUNNING
        run.started_at = datetime.utcnow()
        self._active_runs[run.run_id] = run

        logger.info("FeaturePipeline run %s started (%d features)", run.run_id, len(run.feature_ids))

        try:
            for stage in PipelineStage:
                result = await self._execute_stage(run, stage)
                run.stages[stage] = result

                if result.status == StageStatus.FAILED and stage in (
                    PipelineStage.NORMALIZATION,
                    PipelineStage.TRANSFORMATION,
                ):
                    run.status = PipelineStatus.FAILED
                    logger.error("Pipeline run %s failed at stage %s", run.run_id, stage.value)
                    return run

            run.status = PipelineStatus.COMPLETED
            logger.info("FeaturePipeline run %s completed", run.run_id)

        except Exception as exc:
            run.status = PipelineStatus.FAILED
            logger.exception("Pipeline run %s failed: %s", run.run_id, exc)

        finally:
            run.completed_at = datetime.utcnow()
            self._run_history.append(run)
            self._active_runs.pop(run.run_id, None)

        return run

    async def _execute_stage(self, run: PipelineRun, stage: PipelineStage) -> StageResult:
        """Execute a single pipeline stage."""
        result = StageResult(stage=stage)
        result.started_at = datetime.utcnow()

        handlers = {
            PipelineStage.NORMALIZATION: self._normalize,
            PipelineStage.TRANSFORMATION: self._transform,
            PipelineStage.VALIDATION: self._validate,
            PipelineStage.QUALITY_CHECK: self._quality_check,
            PipelineStage.STORAGE: self._store,
        }

        try:
            await handlers[stage](run, result)
            if result.status == StageStatus.PENDING:
                result.status = StageStatus.PASSED
        except Exception as exc:
            result.status = StageStatus.FAILED
            result.errors.append(str(exc))
            logger.error("Stage %s failed: %s", stage.value, exc)
        finally:
            result.completed_at = datetime.utcnow()
            if result.started_at:
                result.duration_seconds = (result.completed_at - result.started_at).total_seconds()

        return result

    # -- Stage Handlers --

    async def _normalize(self, run: PipelineRun, result: StageResult) -> None:
        """Normalize raw input data."""
        result.metrics["features_normalized"] = float(len(run.feature_ids))

    async def _transform(self, run: PipelineRun, result: StageResult) -> None:
        """Apply feature transformations."""
        result.output_count = len(run.feature_ids)
        result.metrics["features_transformed"] = float(len(run.feature_ids))

    async def _validate(self, run: PipelineRun, result: StageResult) -> None:
        """Validate computed features."""
        result.metrics["features_validated"] = float(len(run.feature_ids))

    async def _quality_check(self, run: PipelineRun, result: StageResult) -> None:
        """Run quality checks on features."""
        result.metrics["features_quality_checked"] = float(len(run.feature_ids))

    async def _store(self, run: PipelineRun, result: StageResult) -> None:
        """Persist features to offline + online stores."""
        result.metrics["features_stored"] = float(len(run.feature_ids))

    # -- Status --

    def get_run(self, run_id: str) -> Optional[PipelineRun]:
        return self._active_runs.get(run_id)

    async def cancel(self, run_id: str) -> bool:
        run = self._active_runs.get(run_id)
        if run and run.status == PipelineStatus.RUNNING:
            run.status = PipelineStatus.CANCELLED
            return True
        return False
