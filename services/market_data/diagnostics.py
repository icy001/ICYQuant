"""
Market Data Diagnostics — comprehensive diagnostics for the
normalization pipeline and all sub-components.

Commit 16 Part 1.2
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class DiagnosticLevel(str, Enum):
    """Severity level for diagnostic results."""

    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class DiagnosticResult:
    """Result of a single diagnostic check."""

    check_name: str = ""
    component: str = ""
    level: DiagnosticLevel = DiagnosticLevel.OK
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    duration_us: float = 0.0
    passed: bool = True
    timestamp: Optional[datetime] = None


@dataclass
class DiagnosticReport:
    """Full diagnostic report for the market data system."""

    timestamp: Optional[datetime] = None
    overall_healthy: bool = True
    total_checks: int = 0
    passed_checks: int = 0
    warning_checks: int = 0
    error_checks: int = 0
    results: list[DiagnosticResult] = field(default_factory=list)
    total_duration_ms: float = 0.0

    @property
    def summary(self) -> dict[str, Any]:
        return {
            "healthy": self.overall_healthy,
            "total": self.total_checks,
            "passed": self.passed_checks,
            "warnings": self.warning_checks,
            "errors": self.error_checks,
            "duration_ms": round(self.total_duration_ms, 2),
        }


class MarketDataDiagnostics:
    """
    Comprehensive diagnostics for the market data normalization pipeline.

    Checks across 7 subsystems:
    - Engine: MarketDataEngine health
    - Pipeline: Pipeline throughput and latency
    - Normalizers: Per-asset-class normalizer health
    - Validation: Validator error rates
    - Quality: Quality scores
    - Cache: Cache hit rates
    - Detection: Detector backlogs
    """

    def __init__(self) -> None:
        self._checks: dict[str, Callable[[], DiagnosticResult]] = {}
        self._last_report: Optional[DiagnosticReport] = None

    async def initialize(self) -> None:
        logger.info("MarketDataDiagnostics initialized with %d checks", len(self._checks))

    # ── Registration ───────────────────────────────

    def register_check(
        self, component: str, check_name: str, check_fn: Callable[[], DiagnosticResult]
    ) -> None:
        """Register a diagnostic check."""
        key = f"{component}:{check_name}"
        self._checks[key] = check_fn
        logger.debug("Registered diagnostic check: %s", key)

    # ── Execution ──────────────────────────────────

    async def run_all(self) -> DiagnosticReport:
        """Run all registered diagnostic checks and produce a report."""
        start = time.perf_counter()
        report = DiagnosticReport(
            timestamp=datetime.now(timezone.utc),
        )

        for key, check_fn in self._checks.items():
            result = check_fn()
            result.timestamp = datetime.now(timezone.utc)
            report.results.append(result)
            report.total_checks += 1

            if result.passed:
                report.passed_checks += 1
            else:
                if result.level == DiagnosticLevel.WARNING:
                    report.warning_checks += 1
                else:
                    report.error_checks += 1

        report.overall_healthy = report.error_checks == 0
        report.total_duration_ms = (time.perf_counter() - start) * 1000
        self._last_report = report
        return report

    async def run_component(self, component: str) -> list[DiagnosticResult]:
        """Run checks for a specific component only."""
        results: list[DiagnosticResult] = []
        for key, check_fn in self._checks.items():
            if key.startswith(f"{component}:"):
                result = check_fn()
                result.timestamp = datetime.now(timezone.utc)
                results.append(result)
        return results

    # ── Built-in checks ────────────────────────────

    async def check_pipeline_throughput(
        self, records_per_second: float = 0.0, threshold: float = 100.0
    ) -> DiagnosticResult:
        """Check if pipeline throughput is adequate."""
        passed = records_per_second >= threshold
        return DiagnosticResult(
            check_name="pipeline_throughput",
            component="pipeline",
            level=DiagnosticLevel.OK if passed else DiagnosticLevel.WARNING,
            message=f"Pipeline throughput: {records_per_second:.1f} records/s (threshold: {threshold})",
            details={"throughput": records_per_second, "threshold": threshold},
            passed=passed,
        )

    async def check_error_rate(
        self, error_rate: float = 0.0, threshold: float = 5.0
    ) -> DiagnosticResult:
        """Check if error rate is acceptable."""
        passed = error_rate <= threshold
        level = DiagnosticLevel.OK
        if error_rate > threshold * 2:
            level = DiagnosticLevel.CRITICAL
        elif error_rate > threshold:
            level = DiagnosticLevel.ERROR

        return DiagnosticResult(
            check_name="error_rate",
            component="validation",
            level=level,
            message=f"Error rate: {error_rate:.2f}% (threshold: {threshold}%)",
            details={"error_rate": error_rate, "threshold": threshold},
            passed=passed,
        )

    async def check_cache_health(
        self, hit_rate: float = 0.0, threshold: float = 80.0
    ) -> DiagnosticResult:
        """Check cache hit rate."""
        passed = hit_rate >= threshold
        return DiagnosticResult(
            check_name="cache_health",
            component="cache",
            level=DiagnosticLevel.OK if passed else DiagnosticLevel.WARNING,
            message=f"Cache hit rate: {hit_rate:.1f}% (threshold: {threshold}%)",
            details={"hit_rate": hit_rate, "threshold": threshold},
            passed=passed,
        )

    async def check_quality_score(
        self, score: float = 100.0, threshold: float = 70.0
    ) -> DiagnosticResult:
        """Check overall data quality score."""
        passed = score >= threshold
        return DiagnosticResult(
            check_name="quality_score",
            component="quality",
            level=DiagnosticLevel.OK if passed else DiagnosticLevel.ERROR,
            message=f"Quality score: {score:.1f}/100 (threshold: {threshold})",
            details={"score": score, "threshold": threshold},
            passed=passed,
        )

    # ── Query ──────────────────────────────────────

    async def get_last_report(self) -> Optional[DiagnosticReport]:
        """Get the most recent diagnostic report."""
        return self._last_report

    async def get_failing_checks(self) -> list[DiagnosticResult]:
        """Get all checks that failed in the last report."""
        if not self._last_report:
            return []
        return [r for r in self._last_report.results if not r.passed]

    @property
    def check_count(self) -> int:
        return len(self._checks)
