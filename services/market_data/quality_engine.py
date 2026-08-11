"""
Quality Engine — market data quality assessment with scoring,
trend analysis, and alerting.

Commit 16 Part 1.2
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class QualityDimension(str, Enum):
    """Quality dimensions for assessment."""

    COMPLETENESS = "completeness"     # No missing fields/records
    ACCURACY = "accuracy"             # Values are correct
    TIMELINESS = "timeliness"         # Data arrives on time
    CONSISTENCY = "consistency"       # Cross-field consistency
    UNIQUENESS = "uniqueness"         # No duplicates
    VALIDITY = "validity"             # Conforms to schema
    FRESHNESS = "freshness"           # Not stale


class QualityLevel(str, Enum):
    EXCELLENT = "excellent"     # 90-100
    GOOD = "good"               # 75-89
    FAIR = "fair"               # 50-74
    POOR = "poor"               # 25-49
    CRITICAL = "critical"       # 0-24


@dataclass
class QualityMetric:
    """A single quality metric reading."""

    dimension: QualityDimension = QualityDimension.COMPLETENESS
    score: float = 100.0           # 0-100
    level: QualityLevel = QualityLevel.EXCELLENT
    description: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp_ns: int = 0


@dataclass
class QualityReport:
    """Aggregated quality assessment."""

    instrument_id: str = ""
    exchange_id: str = ""
    overall_score: float = 100.0
    overall_level: QualityLevel = QualityLevel.EXCELLENT
    dimensions: dict[QualityDimension, QualityMetric] = field(default_factory=dict)
    total_records: int = 0
    total_errors: int = 0
    total_warnings: int = 0
    total_gaps: int = 0
    total_duplicates: int = 0
    total_outliers: int = 0
    assessed_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class QualityEngine:
    """
    Market data quality assessment engine.

    Evaluates data across 7 dimensions and produces composite scores
    with alerting when quality drops below thresholds.
    """

    def __init__(self) -> None:
        self._reports: dict[str, list[QualityReport]] = {}
        self._alert_threshold: float = 50.0
        self._window_size: int = 1000

    async def initialize(self) -> None:
        logger.info("QualityEngine initialized (threshold: %.0f%%, window: %d)",
                     self._alert_threshold, self._window_size)

    # ── Assessment ─────────────────────────────────

    async def assess(
        self,
        instrument_id: str,
        exchange_id: str,
        total_records: int = 0,
        error_count: int = 0,
        warning_count: int = 0,
        gap_count: int = 0,
        duplicate_count: int = 0,
        outlier_count: int = 0,
        freshness_ms: float = 0.0,
        completeness_pct: float = 100.0,
    ) -> QualityReport:
        """Assess data quality and generate a report."""

        dimensions: dict[QualityDimension, QualityMetric] = {}

        # Completeness
        comp_score = completeness_pct
        dimensions[QualityDimension.COMPLETENESS] = QualityMetric(
            dimension=QualityDimension.COMPLETENESS,
            score=comp_score,
            level=self._score_to_level(comp_score),
            description=f"Completeness: {comp_score:.1f}%",
            details={"completeness_pct": completeness_pct},
        )

        # Accuracy (derived from error rate)
        error_rate = (error_count / max(total_records, 1)) * 100
        accuracy_score = max(0.0, 100.0 - error_rate * 2)
        dimensions[QualityDimension.ACCURACY] = QualityMetric(
            dimension=QualityDimension.ACCURACY,
            score=accuracy_score,
            level=self._score_to_level(accuracy_score),
            description=f"Accuracy: {accuracy_score:.1f}% (errors: {error_count})",
            details={"error_count": error_count, "error_rate": error_rate},
        )

        # Uniqueness (derived from duplicate rate)
        dup_rate = (duplicate_count / max(total_records, 1)) * 100
        uniqueness_score = max(0.0, 100.0 - dup_rate * 5)
        dimensions[QualityDimension.UNIQUENESS] = QualityMetric(
            dimension=QualityDimension.UNIQUENESS,
            score=uniqueness_score,
            level=self._score_to_level(uniqueness_score),
            description=f"Uniqueness: {uniqueness_score:.1f}% (duplicates: {duplicate_count})",
            details={"duplicate_count": duplicate_count},
        )

        # Freshness
        freshness_score = max(0.0, 100.0 - (freshness_ms / 1000.0) * 10)
        dimensions[QualityDimension.FRESHNESS] = QualityMetric(
            dimension=QualityDimension.FRESHNESS,
            score=freshness_score,
            level=self._score_to_level(freshness_score),
            description=f"Freshness: {freshness_ms:.1f}ms latency",
            details={"freshness_ms": freshness_ms},
        )

        # Validity
        validity_score = accuracy_score  # Proxy from accuracy
        dimensions[QualityDimension.VALIDITY] = QualityMetric(
            dimension=QualityDimension.VALIDITY,
            score=validity_score,
            level=self._score_to_level(validity_score),
            description=f"Validity: {validity_score:.1f}%",
        )

        # Timeliness
        timeliness_score = freshness_score  # Proxy from freshness
        dimensions[QualityDimension.TIMELINESS] = QualityMetric(
            dimension=QualityDimension.TIMELINESS,
            score=timeliness_score,
            level=self._score_to_level(timeliness_score),
            description=f"Timeliness: {timeliness_score:.1f}%",
        )

        # Consistency
        consistency_score = 100.0 - (warning_count / max(total_records, 1)) * 100
        dimensions[QualityDimension.CONSISTENCY] = QualityMetric(
            dimension=QualityDimension.CONSISTENCY,
            score=consistency_score,
            level=self._score_to_level(consistency_score),
            description=f"Consistency: {consistency_score:.1f}% (warnings: {warning_count})",
            details={"warning_count": warning_count},
        )

        # Overall score (weighted average)
        weights = {
            QualityDimension.COMPLETENESS: 0.20,
            QualityDimension.ACCURACY: 0.20,
            QualityDimension.TIMELINESS: 0.15,
            QualityDimension.CONSISTENCY: 0.15,
            QualityDimension.UNIQUENESS: 0.10,
            QualityDimension.VALIDITY: 0.10,
            QualityDimension.FRESHNESS: 0.10,
        }
        overall = sum(
            dimensions[dim].score * weights.get(dim, 0.0)
            for dim in QualityDimension
        )

        report = QualityReport(
            instrument_id=instrument_id,
            exchange_id=exchange_id,
            overall_score=round(overall, 2),
            overall_level=self._score_to_level(overall),
            dimensions=dimensions,
            total_records=total_records,
            total_errors=error_count,
            total_warnings=warning_count,
            total_gaps=gap_count,
            total_duplicates=duplicate_count,
            total_outliers=outlier_count,
            assessed_at=datetime.now(timezone.utc),
        )

        # Store report
        if instrument_id not in self._reports:
            self._reports[instrument_id] = []
        self._reports[instrument_id].append(report)

        # Trim window
        if len(self._reports[instrument_id]) > self._window_size:
            self._reports[instrument_id] = self._reports[instrument_id][-self._window_size:]

        # Alert on poor quality
        if overall < self._alert_threshold:
            logger.warning("QUALITY ALERT: %s overall score %.1f%%", instrument_id, overall)

        return report

    # ── Query ──────────────────────────────────────

    async def get_latest_report(self, instrument_id: str) -> Optional[QualityReport]:
        """Get the most recent quality report for an instrument."""
        reports = self._reports.get(instrument_id, [])
        return reports[-1] if reports else None

    async def get_report_history(
        self, instrument_id: str, limit: int = 100
    ) -> list[QualityReport]:
        """Get quality report history for an instrument."""
        reports = self._reports.get(instrument_id, [])
        return reports[-limit:]

    async def get_trend(self, instrument_id: str, window: int = 50) -> dict[str, list[float]]:
        """Get quality score trends over recent reports."""
        reports = self._reports.get(instrument_id, [])[-window:]
        return {
            "overall": [r.overall_score for r in reports],
            "completeness": [r.dimensions.get(QualityDimension.COMPLETENESS, QualityMetric()).score for r in reports],
            "accuracy": [r.dimensions.get(QualityDimension.ACCURACY, QualityMetric()).score for r in reports],
            "freshness": [r.dimensions.get(QualityDimension.FRESHNESS, QualityMetric()).score for r in reports],
        }

    # ── Configuration ──────────────────────────────

    async def set_alert_threshold(self, threshold: float) -> None:
        """Set the quality alert threshold (0-100)."""
        self._alert_threshold = max(0.0, min(100.0, threshold))

    @property
    def report_count(self) -> int:
        return sum(len(r) for r in self._reports.values())

    # ── Helpers ────────────────────────────────────

    @staticmethod
    def _score_to_level(score: float) -> QualityLevel:
        if score >= 90:
            return QualityLevel.EXCELLENT
        if score >= 75:
            return QualityLevel.GOOD
        if score >= 50:
            return QualityLevel.FAIR
        if score >= 25:
            return QualityLevel.POOR
        return QualityLevel.CRITICAL
