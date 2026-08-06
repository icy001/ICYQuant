"""Scheduler Diagnostics — troubleshooting and debugging utilities.

Provides diagnostics for:
* Engine state inspection
* Queue health
* Schedule conflicts
* Runtime bottlenecks
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .models.schedule import ScheduleDefinition, ScheduleStatus
from .models.job import JobDefinition, JobState

logger = logging.getLogger(__name__)


class DiagnosticsReport:
    """Container for a diagnostics report."""

    def __init__(self) -> None:
        self.checks: List[Dict[str, Any]] = []
        self.summary: Dict[str, Any] = {}

    def add_check(self, name: str, passed: bool, message: str = "", details: Optional[Dict[str, Any]] = None) -> None:
        """Add a diagnostic check result."""
        self.checks.append({
            "name": name,
            "passed": passed,
            "message": message,
            "details": details or {},
        })

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the report."""
        return {
            "checks": self.checks,
            "summary": self.summary,
            "all_passed": all(c["passed"] for c in self.checks),
        }


class SchedulerDiagnostics:
    """Diagnostics utilities for the distributed scheduler.

    Runs diagnostic checks against scheduler components to
    identify issues like queue buildup, stuck jobs, and
    schedule conflicts.

    Usage::

        diag = SchedulerDiagnostics()
        report = diag.run_all(registry, runtime)
    """

    def __init__(self) -> None:
        pass

    def run_all(
        self,
        registry: Any = None,
        runtime: Any = None,
        repository: Any = None,
    ) -> DiagnosticsReport:
        """Run all diagnostic checks and produce a report."""
        report = DiagnosticsReport()

        # Check engine connectivity
        self._check_engine(report, registry, runtime)

        # Check queue health
        self._check_queue_health(report, runtime)

        # Check schedule conflicts
        self._check_schedule_conflicts(report, registry)

        # Check stuck jobs
        self._check_stuck_jobs(report, runtime)

        # Build summary
        passed = sum(1 for c in report.checks if c["passed"])
        total = len(report.checks)
        report.summary = {
            "total_checks": total,
            "passed": passed,
            "failed": total - passed,
            "healthy": total > 0 and passed == total,
        }

        return report

    def _check_engine(
        self, report: DiagnosticsReport, registry: Any, runtime: Any,
    ) -> None:
        """Check that engine components are properly initialized."""
        checks_passed = True
        details: Dict[str, Any] = {}

        if registry is None:
            details["registry"] = "missing"
            checks_passed = False
        else:
            details["registry"] = "ok"
            details["schedule_count"] = getattr(registry, "schedule_count", "unknown")

        if runtime is None:
            details["runtime"] = "missing"
            checks_passed = False
        else:
            details["runtime"] = "ok"
            details["runtime_running"] = getattr(runtime, "is_running", "unknown")

        report.add_check(
            "engine_components",
            checks_passed,
            "Engine components initialized" if checks_passed else "Engine components missing",
            details,
        )

    def _check_queue_health(
        self, report: DiagnosticsReport, runtime: Any,
    ) -> None:
        """Check for queue buildup or bottlenecks."""
        if runtime is None:
            report.add_check("queue_health", False, "Runtime not available")
            return

        queue_length = getattr(runtime._loop, "queue_length", 0) if hasattr(runtime, "_loop") else 0
        active_jobs = 0
        if hasattr(runtime, "_jobs"):
            active_jobs = sum(
                1 for j in runtime._jobs.values()
                if j.state not in (JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED)
            )

        healthy = queue_length < 1000 and active_jobs < 500
        report.add_check(
            "queue_health",
            healthy,
            f"Queue length: {queue_length}, Active jobs: {active_jobs}",
            {"queue_length": queue_length, "active_jobs": active_jobs},
        )

    def _check_schedule_conflicts(
        self, report: DiagnosticsReport, registry: Any,
    ) -> None:
        """Check for conflicting schedules."""
        if registry is None:
            report.add_check("schedule_conflicts", False, "Registry not available")
            return

        try:
            schedules = registry.list_all() if hasattr(registry, "list_all") else []
            # Check for duplicated targets
            targets: Dict[str, List[str]] = {}
            for s in schedules:
                targets.setdefault(s.target, []).append(s.schedule_id)
            conflicts = {t: ids for t, ids in targets.items() if len(ids) > 1}

            healthy = len(conflicts) == 0
            report.add_check(
                "schedule_conflicts",
                healthy,
                f"Found {len(conflicts)} target conflicts" if not healthy else "No schedule conflicts",
                {"conflicts": {t: ids for t, ids in conflicts.items()}},
            )
        except Exception:
            report.add_check("schedule_conflicts", False, "Failed to check", {"error": "exception"})

    def _check_stuck_jobs(
        self, report: DiagnosticsReport, runtime: Any,
    ) -> None:
        """Check for jobs stuck in non-terminal states."""
        if runtime is None:
            report.add_check("stuck_jobs", False, "Runtime not available")
            return

        try:
            from datetime import datetime, timezone, timedelta
            now = datetime.now(timezone.utc)
            stuck_threshold = timedelta(minutes=30)

            stuck_jobs = 0
            if hasattr(runtime, "_jobs"):
                for job in runtime._jobs.values():
                    if job.state in (JobState.RUNNING, JobState.DISPATCHED):
                        if job.updated_at and (now - job.updated_at) > stuck_threshold:
                            stuck_jobs += 1

            healthy = stuck_jobs == 0
            report.add_check(
                "stuck_jobs",
                healthy,
                f"Found {stuck_jobs} potentially stuck jobs" if not healthy else "No stuck jobs detected",
                {"stuck_count": stuck_jobs},
            )
        except Exception:
            report.add_check("stuck_jobs", False, "Failed to check", {"error": "exception"})

    def health_report(self) -> Dict[str, Any]:
        """Produce a health report for diagnostics."""
        return {"status": "ok"}
