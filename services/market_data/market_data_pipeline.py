"""
Market Data Pipeline — the processing pipeline that raw market data
flows through for normalization, validation, and quality checking.

Commit 16 Part 1.2
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from .canonical_model import CanonicalMarketData, DataQuality
from .data_validator import DataValidator
from .duplicate_detector import DuplicateDetector
from .gap_detector import GapDetector
from .market_data_normalizer import MarketDataNormalizer
from .outlier_detector import OutlierDetector
from .quality_engine import QualityEngine
from .schema_validator import SchemaValidator

logger = logging.getLogger(__name__)


class PipelineStage(str, Enum):
    RECEIVED = "received"
    SCHEMA_VALIDATED = "schema_validated"
    NORMALIZED = "normalized"
    DATA_VALIDATED = "data_validated"
    DUPLICATE_CHECKED = "duplicate_checked"
    GAP_CHECKED = "gap_checked"
    OUTLIER_CHECKED = "outlier_checked"
    QUALITY_SCORED = "quality_scored"
    COMPLETED = "completed"
    REJECTED = "rejected"


@dataclass
class PipelineConfig:
    pipeline_id: str = "icyquant-md-pipeline"
    enable_schema_validation: bool = True
    enable_normalization: bool = True
    enable_data_validation: bool = True
    enable_duplicate_detection: bool = True
    enable_gap_detection: bool = True
    enable_outlier_detection: bool = True
    enable_quality_scoring: bool = True

    max_pipeline_depth: int = 10_000
    rejection_threshold: float = 0.95  # Reject if quality below this
    skip_on_schema_failure: bool = True


@dataclass
class PipelineTrace:
    """Tracing record for a single event through the pipeline."""
    event_id: str = ""
    stages: list[tuple[PipelineStage, float]] = field(default_factory=list)
    total_latency_ms: float = 0.0
    rejected: bool = False
    reject_reason: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class MarketDataPipeline:
    """
    Multi-stage processing pipeline for raw market data.

    Stages:
        Schema Validation → Normalization → Data Validation →
        Duplicate Check → Gap Check → Outlier Check →
        Quality Scoring → Complete (or Reject)
    """

    def __init__(self, config: Optional[PipelineConfig] = None) -> None:
        self.config = config or PipelineConfig()

        self._schema_validator: Optional[SchemaValidator] = None
        self._normalizer: Optional[MarketDataNormalizer] = None
        self._data_validator: Optional[DataValidator] = None
        self._duplicate_detector: Optional[DuplicateDetector] = None
        self._gap_detector: Optional[GapDetector] = None
        self._outlier_detector: Optional[OutlierDetector] = None
        self._quality_engine: Optional[QualityEngine] = None

        self._traces: dict[str, PipelineTrace] = {}
        self._processed_count: int = 0
        self._rejected_count: int = 0

    async def initialize(self) -> None:
        if self.config.enable_schema_validation:
            self._schema_validator = SchemaValidator()
        self._normalizer = MarketDataNormalizer()
        await self._normalizer.initialize()
        if self.config.enable_data_validation:
            self._data_validator = DataValidator()
        if self.config.enable_duplicate_detection:
            self._duplicate_detector = DuplicateDetector()
        if self.config.enable_gap_detection:
            self._gap_detector = GapDetector()
        if self.config.enable_outlier_detection:
            self._outlier_detector = OutlierDetector()
        if self.config.enable_quality_scoring:
            self._quality_engine = QualityEngine()

        logger.info("MarketDataPipeline [%s] initialized", self.config.pipeline_id)

    async def process(self, raw_data: dict[str, Any]) -> Optional[CanonicalMarketData]:
        """
        Run raw market data through all enabled pipeline stages.

        Returns the canonical event, or None if rejected at any stage.
        """
        trace = PipelineTrace(
            event_id=raw_data.get("event_id", ""),
            started_at=datetime.now(timezone.utc),
        )
        stage_start = time.monotonic()

        current_data: Any = raw_data
        current_stage = PipelineStage.RECEIVED
        trace.stages.append((current_stage, 0))

        try:
            # Stage 1: Schema Validation
            if self.config.enable_schema_validation and self._schema_validator:
                result = await self._schema_validator.validate(raw_data)
                if not result.is_valid and self.config.skip_on_schema_failure:
                    trace.rejected = True
                    trace.reject_reason = f"schema_validation: {result.errors}"
                    return None
                current_stage = PipelineStage.SCHEMA_VALIDATED
                trace.stages.append((current_stage, self._elapsed_ms(stage_start)))

            # Stage 2: Normalization
            if self.config.enable_normalization and self._normalizer:
                canonical = await self._normalizer.normalize(raw_data)
                if canonical is None:
                    trace.rejected = True
                    trace.reject_reason = "normalization_failed"
                    return None
                current_stage = PipelineStage.NORMALIZED
                trace.stages.append((current_stage, self._elapsed_ms(stage_start)))

            # Stage 3: Data Validation
            if self.config.enable_data_validation and self._data_validator:
                valid = await self._data_validator.validate(canonical)
                if not valid:
                    canonical.quality = DataQuality.SUSPECT
                    canonical.quality_flags.append("data_validation_failed")
                current_stage = PipelineStage.DATA_VALIDATED
                trace.stages.append((current_stage, self._elapsed_ms(stage_start)))

            # Stage 4: Duplicate Detection
            if self.config.enable_duplicate_detection and self._duplicate_detector:
                is_dup = await self._duplicate_detector.check(canonical)
                if is_dup:
                    canonical.quality_flags.append("duplicate")
                current_stage = PipelineStage.DUPLICATE_CHECKED
                trace.stages.append((current_stage, self._elapsed_ms(stage_start)))

            # Stage 5: Gap Detection
            if self.config.enable_gap_detection and self._gap_detector:
                has_gap = await self._gap_detector.check(canonical)
                if has_gap:
                    canonical.quality_flags.append("gap_detected")
                current_stage = PipelineStage.GAP_CHECKED
                trace.stages.append((current_stage, self._elapsed_ms(stage_start)))

            # Stage 6: Outlier Detection
            if self.config.enable_outlier_detection and self._outlier_detector:
                is_outlier = await self._outlier_detector.check(canonical)
                if is_outlier:
                    canonical.quality_flags.append("outlier")
                    canonical.quality = DataQuality.SUSPECT
                current_stage = PipelineStage.OUTLIER_CHECKED
                trace.stages.append((current_stage, self._elapsed_ms(stage_start)))

            # Stage 7: Quality Scoring
            if self.config.enable_quality_scoring and self._quality_engine:
                score = await self._quality_engine.score(canonical)
                canonical.quality_score = score
                canonical.quality = self._quality_engine.classify(score)
                current_stage = PipelineStage.QUALITY_SCORED
                trace.stages.append((current_stage, self._elapsed_ms(stage_start)))

            # Final rejection check
            if canonical.quality_score < self.config.rejection_threshold:
                canonical.quality = DataQuality.REJECTED
                trace.rejected = True
                trace.reject_reason = f"quality_below_threshold: {canonical.quality_score}"
                self._rejected_count += 1

            current_stage = PipelineStage.COMPLETED
            trace.stages.append((current_stage, self._elapsed_ms(stage_start)))
            trace.completed_at = datetime.now(timezone.utc)
            trace.total_latency_ms = self._elapsed_ms(stage_start)

            self._traces[canonical.event_id] = trace
            self._processed_count += 1

            return canonical

        except Exception:
            logger.exception("Pipeline stage failure")
            trace.rejected = True
            trace.reject_reason = "pipeline_exception"
            self._rejected_count += 1
            return None

    async def status(self) -> dict[str, Any]:
        return {
            "pipeline_id": self.config.pipeline_id,
            "processed": self._processed_count,
            "rejected": self._rejected_count,
            "active_traces": len(self._traces),
        }

    def get_trace(self, event_id: str) -> Optional[PipelineTrace]:
        return self._traces.get(event_id)

    @staticmethod
    def _elapsed_ms(start: float) -> float:
        return (time.monotonic() - start) * 1000
