"""
Quality Catalog — tracks data quality metrics, dimensions, and historical
quality records for data lake datasets.

Commit 16 Part 1.3
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class QualityDimension(str, Enum):
    COMPLETENESS = "completeness"
    ACCURACY = "accuracy"
    CONSISTENCY = "consistency"
    TIMELINESS = "timeliness"
    UNIQUENESS = "uniqueness"
    VALIDITY = "validity"
    FRESHNESS = "freshness"


class QualityMetric(str, Enum):
    NULL_RATIO = "null_ratio"
    DUPLICATE_RATIO = "duplicate_ratio"
    OUTLIER_COUNT = "outlier_count"
    GAP_COUNT = "gap_count"
    LATENCY_MS = "latency_ms"
    STALENESS_MS = "staleness_ms"
    SCHEMA_COMPLIANCE = "schema_compliance"
    VALUE_RANGE_VIOLATIONS = "value_range_violations"
    RECORD_COUNT = "record_count"


@dataclass
class QualityRecord:
    dataset: str
    version_id: str
    metrics: dict[str, float] = field(default_factory=dict)
    dimensions: dict[str, float] = field(default_factory=dict)
    overall_score: float = 0.0
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    partition: str = ""
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    passed: bool = True


class QualityCatalog:
    """
    Tracks and manages data quality metrics across all data lake datasets.

    Provides quality scoring, trend analysis, and threshold-based alerting
    across multiple quality dimensions.
    """

    def __init__(self) -> None:
        self._records: dict[str, list[QualityRecord]] = {}
        self._thresholds: dict[str, dict[str, float]] = {}
        self._quality_scores: dict[str, float] = {}

    async def record(self, record: QualityRecord) -> None:
        """Record a quality check result."""
        if record.dataset not in self._records:
            self._records[record.dataset] = []
        self._records[record.dataset].append(record)

        # Update rolling quality score
        self._quality_scores[record.dataset] = record.overall_score

        if not record.passed:
            logger.warning(
                "Quality check FAILED for %s v%s (score=%.2f): %s",
                record.dataset, record.version_id, record.overall_score,
                ", ".join(record.errors),
            )
        else:
            logger.debug(
                "Quality check PASSED for %s v%s (score=%.2f)",
                record.dataset, record.version_id, record.overall_score,
            )

    async def get_latest(self, dataset: str) -> Optional[QualityRecord]:
        """Get the most recent quality record for a dataset."""
        records = self._records.get(dataset, [])
        return records[-1] if records else None

    async def get_score(self, dataset: str) -> float:
        """Get the current quality score for a dataset."""
        return self._quality_scores.get(dataset, 0.0)

    async def get_history(
        self, dataset: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get quality history for a dataset."""
        records = self._records.get(dataset, [])
        return [
            {
                "version_id": r.version_id,
                "overall_score": r.overall_score,
                "passed": r.passed,
                "checked_at": r.checked_at.isoformat(),
                "errors": r.errors,
            }
            for r in records[-limit:]
        ]

    async def set_threshold(
        self, dataset: str, metric: str, min_value: float, max_value: Optional[float] = None
    ) -> None:
        """Set quality thresholds for a dataset."""
        if dataset not in self._thresholds:
            self._thresholds[dataset] = {}
        self._thresholds[dataset][metric] = min_value

    async def get_thresholds(self, dataset: str) -> dict[str, float]:
        """Get quality thresholds for a dataset."""
        return self._thresholds.get(dataset, {})

    async def compute_dimension_score(
        self, metrics: dict[str, float]
    ) -> dict[str, float]:
        """Compute dimension-level scores from individual metrics."""
        dimension_metrics = {
            QualityDimension.COMPLETENESS: [QualityMetric.NULL_RATIO],
            QualityDimension.UNIQUENESS: [QualityMetric.DUPLICATE_RATIO],
            QualityDimension.TIMELINESS: [QualityMetric.LATENCY_MS, QualityMetric.STALENESS_MS],
            QualityDimension.VALIDITY: [QualityMetric.SCHEMA_COMPLIANCE, QualityMetric.VALUE_RANGE_VIOLATIONS],
        }

        scores: dict[str, float] = {}
        for dim, dim_metrics in dimension_metrics.items():
            values = [metrics.get(m.value, 0.0) for m in dim_metrics]
            scores[dim.value] = sum(values) / len(values) if values else 0.0

        return scores
