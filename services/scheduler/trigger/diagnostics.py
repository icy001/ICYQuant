"""Trigger Diagnostics — debugging and diagnostic tools for the trigger engine.

The :class:`TriggerDiagnostics` provides:
* Trigger configuration inspection
* Queue congestion analysis
* Misfire pattern detection
* Stuck trigger detection
* Dependency graph visualization data
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class DiagnosticsReport:
    """A complete diagnostics snapshot of the trigger engine."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    engine_status: str = "unknown"
    trigger_count: int = 0
    active_triggers: int = 0
    queue_depth: int = 0
    queue_congestion: str = "normal"
    misfire_summary: Dict[str, Any] = field(default_factory=dict)
    stuck_triggers: List[Dict[str, Any]] = field(default_factory=list)
    dependency_warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "engine_status": self.engine_status,
            "trigger_count": self.trigger_count,
            "active_triggers": self.active_triggers,
            "queue_depth": self.queue_depth,
            "queue_congestion": self.queue_congestion,
            "misfire_summary": self.misfire_summary,
            "stuck_triggers": self.stuck_triggers,
            "dependency_warnings": self.dependency_warnings,
            "recommendations": self.recommendations,
        }


class TriggerDiagnostics:
    """Diagnostics and debugging tools for the trigger engine.

    Usage::

        diag = TriggerDiagnostics()
        report = diag.run_full_diagnostics(engine, manager, queue)
    """

    def __init__(self) -> None:
        self._last_report: Optional[DiagnosticsReport] = None

    # ------------------------------------------------------------------
    # Full diagnostics
    # ------------------------------------------------------------------

    def run_full_diagnostics(
        self,
        engine: Any,
        manager: Any,
        queue: Any,
        misfire_handler: Any,
    ) -> DiagnosticsReport:
        """Run a complete diagnostics pass and return a report."""
        report = DiagnosticsReport()

        # Engine status
        report.engine_status = getattr(engine, "_state", "unknown")

        # Trigger counts
        report.trigger_count = getattr(manager, "get_trigger_count", lambda: 0)()
        active = getattr(manager, "list_triggers", lambda: [])()
        report.active_triggers = sum(1 for t in active if t.get("enabled", False))

        # Queue analysis
        report.queue_depth = len(queue) if hasattr(queue, "__len__") else 0
        report.queue_congestion = self._assess_congestion(report.queue_depth, queue)

        # Misfire analysis
        report.misfire_summary = self._analyze_misfires(misfire_handler)

        # Stuck trigger detection
        report.stuck_triggers = self._detect_stuck_triggers(manager)

        # Dependency warnings
        report.dependency_warnings = self._check_dependencies(manager)

        # Recommendations
        report.recommendations = self._generate_recommendations(report)

        self._last_report = report
        return report

    # ------------------------------------------------------------------
    # Queue congestion
    # ------------------------------------------------------------------

    def check_queue_congestion(self, queue: Any) -> Dict[str, Any]:
        """Analyze queue health and congestion level."""
        depth = len(queue) if hasattr(queue, "__len__") else 0
        max_size = getattr(queue, "_max_size", 100_000)
        utilization = depth / max(max_size, 1) * 100

        level = "normal"
        if utilization > 90:
            level = "critical"
        elif utilization > 70:
            level = "warning"
        elif utilization > 50:
            level = "elevated"

        return {
            "depth": depth,
            "max_size": max_size,
            "utilization_pct": round(utilization, 2),
            "level": level,
        }

    def _assess_congestion(self, depth: int, queue: Any) -> str:
        max_size = getattr(queue, "_max_size", 100_000)
        pct = depth / max(max_size, 1) * 100
        if pct > 90:
            return "critical"
        if pct > 70:
            return "warning"
        if pct > 50:
            return "elevated"
        return "normal"

    # ------------------------------------------------------------------
    # Misfire analysis
    # ------------------------------------------------------------------

    def analyze_misfire_patterns(self, misfire_handler: Any) -> Dict[str, Any]:
        """Analyze misfire patterns to detect systemic issues."""
        recent = (
            getattr(misfire_handler, "get_recent_misfires", lambda _: [])(100)
            if misfire_handler
            else []
        )
        if not recent:
            return {"total": 0, "pattern": "none"}

        # Count by trigger
        by_trigger: Dict[str, int] = {}
        for m in recent:
            tid = m.get("trigger_id", "?")
            by_trigger[tid] = by_trigger.get(tid, 0) + 1

        # Find triggers with excessive misfires
        excessive = [
            {"trigger_id": k, "count": v}
            for k, v in by_trigger.items()
            if v > 10
        ]

        return {
            "total": len(recent),
            "unique_triggers": len(by_trigger),
            "excessive_misfires": excessive,
            "pattern": "concentrated" if excessive else "scattered",
        }

    def _analyze_misfires(self, misfire_handler: Any) -> Dict[str, Any]:
        if misfire_handler is None:
            return {"total": 0}
        return self.analyze_misfire_patterns(misfire_handler)

    # ------------------------------------------------------------------
    # Stuck trigger detection
    # ------------------------------------------------------------------

    def detect_stuck_triggers(self, manager: Any) -> List[Dict[str, Any]]:
        """Detect triggers that haven't fired in an unusually long time."""
        triggers = getattr(manager, "list_triggers", lambda: [])()
        now = datetime.now(timezone.utc)
        stuck: List[Dict[str, Any]] = []

        for t in triggers:
            last_fired_str = t.get("last_fired_at")
            if last_fired_str is None:
                continue
            try:
                last_fired = datetime.fromisoformat(last_fired_str)
                idle_seconds = (now - last_fired).total_seconds()
                # Flag triggers idle > 1 hour
                if idle_seconds > 3600:
                    stuck.append({
                        "trigger_id": t["trigger_id"],
                        "last_fired_at": last_fired_str,
                        "idle_seconds": idle_seconds,
                        "enabled": t.get("enabled", False),
                    })
            except (ValueError, TypeError):
                pass

        return stuck

    def _detect_stuck_triggers(self, manager: Any) -> List[Dict[str, Any]]:
        return self.detect_stuck_triggers(manager)

    # ------------------------------------------------------------------
    # Dependency checking
    # ------------------------------------------------------------------

    def check_dependency_health(self, manager: Any) -> List[str]:
        """Check for dependency-related issues across all triggers."""
        warnings: List[str] = []
        triggers = getattr(manager, "list_triggers", lambda: [])()
        trigger_ids = {t.get("trigger_id") for t in triggers}

        for t in triggers:
            deps = t.get("depends_on", [])
            for dep in deps:
                if dep not in trigger_ids:
                    warnings.append(
                        f"Trigger '{t.get('trigger_id')}' depends on "
                        f"unknown trigger '{dep}'"
                    )

        return warnings

    def _check_dependencies(self, manager: Any) -> List[str]:
        return self.check_dependency_health(manager)

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    def _generate_recommendations(self, report: DiagnosticsReport) -> List[str]:
        recs: List[str] = []

        if report.queue_congestion in ("critical", "warning"):
            recs.append(
                f"Queue congestion is {report.queue_congestion}. "
                "Consider scaling out dispatch workers or increasing max queue size."
            )

        if report.stuck_triggers:
            recs.append(
                f"Found {len(report.stuck_triggers)} potentially stuck triggers. "
                "Review if they should be re-enabled or removed."
            )

        if report.misfire_summary.get("excessive_misfires"):
            recs.append(
                "Some triggers have excessive misfires. "
                "Check system clock, network connectivity, and trigger configurations."
            )

        if report.dependency_warnings:
            recs.append(
                f"Found {len(report.dependency_warnings)} dependency issues. "
                "Verify that all upstream triggers are registered."
            )

        if report.active_triggers == 0 and report.trigger_count > 0:
            recs.append("All triggers are disabled. Enable triggers to start scheduling.")

        if not recs:
            recs.append("No issues detected. The trigger engine is healthy.")

        return recs

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        return {
            "last_report": self._last_report.to_dict() if self._last_report else None,
            "status": "ready",
        }
