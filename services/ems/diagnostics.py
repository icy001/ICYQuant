"""EMS Diagnostics — Execution diagnostics and troubleshooting.

Provides diagnostic capabilities for the Execution Management System,
including stuck order detection, performance analysis, and health
diagnostics.

Checks:
    - Stuck orders (no fills for extended period)
    - Slow executions (below expected fill rate)
    - Excessive slippage
    - Queue congestion
    - Strategy errors

Usage::

    diagnostics = EMSDiagnostics()
    issues = await diagnostics.check_execution(task_id)
    health = await diagnostics.system_health()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class IssueSeverity(str, Enum):
    """Diagnostic issue severity."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class DiagnosticIssue:
    """A diagnostic issue found during inspection.

    Attributes:
        code: Issue code for categorization
        message: Human-readable description
        severity: Issue severity level
        component: Affected component
        suggestion: Suggested remediation
        timestamp: When the issue was detected
        metadata: Additional context
    """

    code: str = ""
    message: str = ""
    severity: IssueSeverity = IssueSeverity.WARNING
    component: str = ""
    suggestion: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "component": self.component,
            "suggestion": self.suggestion,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class DiagnosticReport:
    """Aggregated diagnostic report.

    Attributes:
        component: Component being diagnosed
        status: Overall health status
        issues: List of diagnostic issues
        metrics: Related metrics
        generated_at: Report generation time
    """

    component: str = ""
    status: str = "healthy"
    issues: list[DiagnosticIssue] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def has_critical(self) -> bool:
        return any(i.severity == IssueSeverity.CRITICAL for i in self.issues)

    @property
    def has_errors(self) -> bool:
        return any(i.severity in (IssueSeverity.ERROR, IssueSeverity.CRITICAL) for i in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "status": self.status,
            "issues": [i.to_dict() for i in self.issues],
            "metrics": self.metrics,
            "generated_at": self.generated_at.isoformat(),
            "has_critical": self.has_critical,
            "has_errors": self.has_errors,
        }


class EMSDiagnostics:
    """Execution diagnostics and troubleshooting.

    Performs health checks and diagnostics on the EMS components
    including execution engine, scheduler, and algorithm strategies.

    Attributes:
        _issues: Recorded diagnostic issues
        _thresholds: Diagnostic thresholds
    """

    def __init__(self) -> None:
        self._issues: list[DiagnosticIssue] = []
        self._thresholds: dict[str, Any] = {
            "max_stuck_duration_seconds": 300.0,  # 5 minutes
            "min_fill_rate_per_min": 0.01,  # qty/min
            "max_slippage_bps": 50.0,
            "max_queue_depth": 1000,
            "max_error_rate": 0.05,  # 5%
        }

    # ── Diagnostic Checks ──────────────────────────────────────────

    async def check_execution(
        self,
        task_id: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> DiagnosticReport:
        """Run diagnostics on a specific execution task.

        Checks for:
            - Stuck orders (no fills)
            - Slow fill rate
            - Excessive slippage

        Args:
            task_id: Execution task identifier
            metadata: Execution metadata for analysis

        Returns:
            DiagnosticReport
        """
        issues: list[DiagnosticIssue] = []

        if not metadata:
            return DiagnosticReport(
                component=f"execution:{task_id}",
                status="unknown",
                issues=issues,
            )

        # Check for stuck order
        fill_pct = metadata.get("fill_pct", 0.0)
        duration = metadata.get("duration_seconds", 0.0)
        if fill_pct < 0.01 and duration > self._thresholds["max_stuck_duration_seconds"]:
            issues.append(DiagnosticIssue(
                code="EXEC_STUCK",
                message=f"Execution stuck: fill_pct={fill_pct:.2%} after {duration:.0f}s",
                severity=IssueSeverity.WARNING,
                component=f"execution:{task_id}",
                suggestion="Consider pausing or switching strategy",
                metadata={"fill_pct": fill_pct, "duration": duration},
            ))

        # Check fill rate
        fill_rate = metadata.get("fill_rate_per_min", 0.0)
        if fill_rate > 0 and fill_rate < self._thresholds["min_fill_rate_per_min"]:
            issues.append(DiagnosticIssue(
                code="EXEC_SLOW_FILL",
                message=f"Slow fill rate: {fill_rate:.2f}/min",
                severity=IssueSeverity.INFO,
                component=f"execution:{task_id}",
                suggestion="Market may have low liquidity",
            ))

        # Check slippage
        slippage = metadata.get("slippage_bps", 0.0)
        if abs(slippage) > self._thresholds["max_slippage_bps"]:
            issues.append(DiagnosticIssue(
                code="EXEC_HIGH_SLIPPAGE",
                message=f"High slippage: {slippage:.1f} bps",
                severity=IssueSeverity.WARNING,
                component=f"execution:{task_id}",
                suggestion="Consider using limit orders or reducing urgency",
            ))

        # Determine status
        if any(i.severity == IssueSeverity.CRITICAL for i in issues):
            status = "critical"
        elif any(i.severity == IssueSeverity.ERROR for i in issues):
            status = "degraded"
        elif issues:
            status = "warning"
        else:
            status = "healthy"

        return DiagnosticReport(
            component=f"execution:{task_id}",
            status=status,
            issues=issues,
            metrics=metadata,
        )

    async def check_scheduler(self, scheduler_state: Optional[dict[str, Any]] = None) -> DiagnosticReport:
        """Run diagnostics on the execution scheduler.

        Args:
            scheduler_state: Scheduler state dictionary

        Returns:
            DiagnosticReport
        """
        issues: list[DiagnosticIssue] = []

        if scheduler_state:
            queue_depth = scheduler_state.get("queue_depth", 0)
            if queue_depth > self._thresholds["max_queue_depth"]:
                issues.append(DiagnosticIssue(
                    code="SCHED_QUEUE_DEEP",
                    message=f"Scheduler queue depth {queue_depth} exceeds limit",
                    severity=IssueSeverity.WARNING,
                    component="scheduler",
                    suggestion="Increase max concurrent or add capacity",
                ))

        status = "warning" if issues else "healthy"
        return DiagnosticReport(
            component="scheduler",
            status=status,
            issues=issues,
            metrics=scheduler_state or {},
        )

    async def check_dispatcher(self, dispatcher_state: Optional[dict[str, Any]] = None) -> DiagnosticReport:
        """Run diagnostics on the execution dispatcher.

        Args:
            dispatcher_state: Dispatcher state dictionary

        Returns:
            DiagnosticReport
        """
        issues: list[DiagnosticIssue] = []

        if dispatcher_state:
            controller = dispatcher_state.get("controller", {})
            if controller.get("circuit_open"):
                issues.append(DiagnosticIssue(
                    code="DISP_CIRCUIT_OPEN",
                    message="Dispatcher circuit breaker is open",
                    severity=IssueSeverity.ERROR,
                    component="dispatcher",
                    suggestion="Check broker connectivity",
                ))

        status = "error" if issues else "healthy"
        return DiagnosticReport(
            component="dispatcher",
            status=status,
            issues=issues,
            metrics=dispatcher_state or {},
        )

    async def system_health(self, component_states: Optional[dict[str, Any]] = None) -> DiagnosticReport:
        """Run comprehensive system health diagnostics.

        Args:
            component_states: Dict of component → state

        Returns:
            DiagnosticReport
        """
        all_issues: list[DiagnosticIssue] = []

        if component_states:
            for component, state in component_states.items():
                if component == "scheduler":
                    report = await self.check_scheduler(state)
                    all_issues.extend(report.issues)
                elif component == "dispatcher":
                    report = await self.check_dispatcher(state)
                    all_issues.extend(report.issues)

        if any(i.severity == IssueSeverity.CRITICAL for i in all_issues):
            status = "critical"
        elif any(i.severity == IssueSeverity.ERROR for i in all_issues):
            status = "degraded"
        elif all_issues:
            status = "warning"
        else:
            status = "healthy"

        return DiagnosticReport(
            component="ems",
            status=status,
            issues=all_issues,
            metrics=component_states or {},
        )

    # ── Threshold Management ───────────────────────────────────────

    def set_threshold(self, name: str, value: Any) -> None:
        """Set a diagnostic threshold.

        Args:
            name: Threshold name
            value: Threshold value
        """
        self._thresholds[name] = value

    def to_dict(self) -> dict[str, Any]:
        """Serialize diagnostics state."""
        return {
            "thresholds": self._thresholds,
            "issues_count": len(self._issues),
        }
