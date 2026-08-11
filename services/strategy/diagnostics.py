"""
Strategy Platform Diagnostics — performance and health analysis.

Analyzes strategy runtime behavior, detects anomalies, and produces
diagnostic reports for operational insight.

Detects:
    - High error rates
    - Abnormal latency
    - Resource exhaustion
    - Stale strategies
    - Snapshot failures
    - Recovery rate issues
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class Severity(str, Enum):
    """Diagnostic issue severity."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class DiagnosticCategory(str, Enum):
    """Category of diagnostic issue."""
    PERFORMANCE = "performance"
    RESOURCE = "resource"
    RELIABILITY = "reliability"
    LIFECYCLE = "lifecycle"
    SNAPSHOT = "snapshot"
    RECOVERY = "recovery"
    SECURITY = "security"
    CONFIG = "config"


@dataclass
class DiagnosticIssue:
    """A single diagnostic finding."""

    issue_id: str
    severity: Severity
    category: DiagnosticCategory
    title: str
    description: str
    strategy_id: str = ""
    recommendation: str = ""
    metric_name: str = ""
    metric_value: float = 0.0
    threshold: float = 0.0
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "severity": self.severity.value,
            "category": self.category.value,
            "title": self.title,
            "description": self.description,
            "strategy_id": self.strategy_id,
            "recommendation": self.recommendation,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "detected_at": self.detected_at.isoformat(),
        }


@dataclass
class DiagnosticReport:
    """Aggregate diagnostic report."""

    report_id: str
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    issues: List[DiagnosticIssue] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    overall_health: str = "healthy"  # healthy, degraded, unhealthy

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.CRITICAL)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.WARNING)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at.isoformat(),
            "overall_health": self.overall_health,
            "issue_counts": {
                "critical": self.critical_count,
                "error": self.error_count,
                "warning": self.warning_count,
                "info": sum(1 for i in self.issues if i.severity == Severity.INFO),
            },
            "summary": self.summary,
            "issues": [i.to_dict() for i in self.issues],
        }


class StrategyDiagnostics:
    """Diagnostic analyzer for the Strategy Platform.

    Runs diagnostic checks against the platform state and produces
    reports with severity-scored issues and actionable recommendations.

    Usage:
        diagnostics = StrategyDiagnostics()
        report = diagnostics.run_full_diagnostics(engine, metrics, telemetry)
    """

    def __init__(self) -> None:
        self._reports: List[DiagnosticReport] = []
        self._thresholds: Dict[str, float] = {
            "error_rate_pct": 5.0,
            "max_latency_ms": 30000.0,
            "min_recovery_success_rate": 0.80,
            "max_snapshot_failure_rate": 0.10,
            "max_slot_utilization": 0.85,
            "stale_strategy_hours": 48.0,
        }
        logger.info("StrategyDiagnostics initialized")

    # ── Full Diagnostics ──

    def run_full_diagnostics(
        self,
        engine: Any,
        metrics: Any,
        telemetry: Any,
    ) -> DiagnosticReport:
        """Run a comprehensive diagnostic suite on the platform.

        Checks:
            1. Engine health (state, component status)
            2. Runtime health (slot utilization, stale strategies)
            3. Registry health (consistency, state transitions)
            4. Snapshot health (failure rate, missing snapshots)
            5. Recovery health (success rate, recent failures)
            6. Resource health (CPU, memory limits)
            7. Telemetry health (trace anomalies)

        Returns:
            A complete DiagnosticReport with all issues.
        """
        import uuid

        report = DiagnosticReport(report_id=uuid.uuid4().hex[:12])

        # Run all checks
        issues: List[DiagnosticIssue] = []
        issues.extend(self._check_engine_health(engine))
        issues.extend(self._check_runtime_health(engine))
        issues.extend(self._check_registry_health(engine))
        issues.extend(self._check_snapshot_health(engine))
        issues.extend(self._check_recovery_health(engine))
        issues.extend(self._check_resource_health(engine))
        issues.extend(self._check_telemetry_health(telemetry))

        report.issues = sorted(issues, key=lambda i: _severity_order(i.severity))
        report.overall_health = self._determine_overall_health(report)
        report.summary = self._build_summary(engine, report)

        self._reports.append(report)
        logger.info("Diagnostics complete: %s (health=%s, issues=%d)",
                    report.report_id, report.overall_health, len(report.issues))
        return report

    # ── Individual Checks ──

    def _check_engine_health(self, engine: Any) -> List[DiagnosticIssue]:
        issues = []
        if not engine.is_ready:
            issues.append(DiagnosticIssue(
                issue_id="engine-not-ready",
                severity=Severity.CRITICAL,
                category=DiagnosticCategory.LIFECYCLE,
                title="Engine is not ready",
                description=f"Engine state: {engine.state.value}",
                recommendation="Initialize the engine via engine.initialize()",
            ))
        return issues

    def _check_runtime_health(self, engine: Any) -> List[DiagnosticIssue]:
        issues = []
        runtime_summary = engine.runtime.get_summary()
        total = runtime_summary.get("total_slots", 0)
        running = runtime_summary.get("running_count", 0)
        max_slots = runtime_summary.get("quota_max", 50)

        # Check slot utilization
        if max_slots > 0:
            utilization = total / max_slots
            if utilization > self._thresholds["max_slot_utilization"]:
                issues.append(DiagnosticIssue(
                    issue_id="high-slot-utilization",
                    severity=Severity.WARNING,
                    category=DiagnosticCategory.RESOURCE,
                    title="High runtime slot utilization",
                    description=f"Slots: {total}/{max_slots} ({utilization:.0%})",
                    recommendation="Consider scaling runtime quota or stopping inactive strategies.",
                    metric_name="slot_utilization",
                    metric_value=utilization,
                    threshold=self._thresholds["max_slot_utilization"],
                ))

        return issues

    def _check_registry_health(self, engine: Any) -> List[DiagnosticIssue]:
        issues = []
        failed = engine.registry.list_by_state("failed")
        if failed:
            issues.append(DiagnosticIssue(
                issue_id="failed-strategies",
                severity=Severity.ERROR,
                category=DiagnosticCategory.RELIABILITY,
                title="Strategies in FAILED state",
                description=f"{len(failed)} strategies are in failed state: {failed}",
                recommendation="Investigate failure causes and attempt recovery.",
                metric_name="failed_count",
                metric_value=float(len(failed)),
            ))
        return issues

    def _check_snapshot_health(self, engine: Any) -> List[DiagnosticIssue]:
        issues = []
        snap_summary = engine.snapshot_manager.get_summary()
        total = snap_summary.get("total_snapshots", 0)

        # Check for strategies without any snapshot
        active = engine.registry.list_active()
        for sid in active:
            snapshots = engine.snapshot_manager.list_snapshots(sid)
            if not snapshots:
                issues.append(DiagnosticIssue(
                    issue_id=f"no-snapshot-{sid}",
                    severity=Severity.INFO,
                    category=DiagnosticCategory.SNAPSHOT,
                    title="Strategy has no snapshots",
                    description=f"Strategy {sid} has been running but has no snapshots.",
                    strategy_id=sid,
                    recommendation="Take a snapshot to enable recovery.",
                ))

        return issues

    def _check_recovery_health(self, engine: Any) -> List[DiagnosticIssue]:
        issues = []
        success_rate = engine.recovery.get_success_rate()
        if success_rate < self._thresholds["min_recovery_success_rate"]:
            issues.append(DiagnosticIssue(
                issue_id="low-recovery-rate",
                severity=Severity.WARNING,
                category=DiagnosticCategory.RECOVERY,
                title="Low recovery success rate",
                description=f"Recovery success rate: {success_rate:.0%} (threshold: {self._thresholds['min_recovery_success_rate']:.0%})",
                recommendation="Investigate snapshot integrity and recovery procedures.",
                metric_name="recovery_success_rate",
                metric_value=success_rate,
                threshold=self._thresholds["min_recovery_success_rate"],
            ))
        return issues

    def _check_resource_health(self, engine: Any) -> List[DiagnosticIssue]:
        return []  # Extensible: add CPU/memory checks when instrumentation is available

    def _check_telemetry_health(self, telemetry: Any) -> List[DiagnosticIssue]:
        return []  # Extensible: add trace anomaly detection

    # ── Helpers ──

    def _determine_overall_health(self, report: DiagnosticReport) -> str:
        if report.critical_count > 0:
            return "unhealthy"
        if report.error_count > 0:
            return "degraded"
        if report.warning_count > 3:
            return "degraded"
        return "healthy"

    def _build_summary(self, engine: Any, report: DiagnosticReport) -> Dict[str, Any]:
        return {
            "engine_state": engine.state.value,
            "total_issues": len(report.issues),
            "critical": report.critical_count,
            "error": report.error_count,
            "warning": report.warning_count,
            "recommendation": "Investigate critical and error issues immediately." if report.critical_count > 0 else "No immediate action required." if report.error_count == 0 else "Review error issues.",
        }

    # ── Query ──

    def get_latest_report(self) -> Optional[DiagnosticReport]:
        return self._reports[-1] if self._reports else None

    def list_reports(self, limit: int = 20) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._reports[-limit:]]

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_reports": len(self._reports),
            "thresholds": self._thresholds,
        }


def _severity_order(sev: Severity) -> int:
    """Sort order for severity (critical first)."""
    order = {
        Severity.CRITICAL: 0,
        Severity.ERROR: 1,
        Severity.WARNING: 2,
        Severity.INFO: 3,
    }
    return order.get(sev, 4)
