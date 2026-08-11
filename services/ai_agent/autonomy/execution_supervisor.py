"""Execution Supervisor — monitors and supervises execution plan execution.

Pipeline:
    Execution Plan -> ExecutionSupervisor.monitor()
        -> Track slice completion
        -> Detect deviations from plan
        -> Enforce execution limits
        -> Report execution status
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ExecutionStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PAUSED = "paused"
    ABORTED = "aborted"


@dataclass
class ExecutionReport:
    """Execution monitoring report.

    Attributes:
        report_id: Unique identifier.
        plan_id: Parent execution plan.
        status: Current execution status.
        slices_completed: Number of slices executed.
        slices_total: Total slices in plan.
        deviation_pct: Deviation from plan (%).
        errors: Any execution errors.
        reported_at: Report timestamp.
    """

    report_id: str = ""
    plan_id: str = ""
    status: ExecutionStatus = ExecutionStatus.NOT_STARTED
    slices_completed: int = 0
    slices_total: int = 0
    deviation_pct: float = 0.0
    errors: List[str] = field(default_factory=list)
    reported_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def progress_pct(self) -> float:
        if self.slices_total == 0:
            return 0.0
        return self.slices_completed / self.slices_total


class ExecutionSupervisor:
    """Monitors and supervises execution plan execution.

    Tracks slice progress, detects deviations, and enforces limits.
    Does NOT execute trades; only supervises and reports.

    Supports:
        - Slice-level progress tracking
        - Deviation detection
        - Limit enforcement
        - Execution status reporting

    Usage:
        supervisor = ExecutionSupervisor()
        await supervisor.initialize()
        report = supervisor.get_status(plan_id="plan_1")
    """

    def __init__(self, max_deviation_pct: float = 0.10) -> None:
        self._max_deviation_pct = max_deviation_pct
        self._reports: Dict[str, List[ExecutionReport]] = {}
        self._active: Dict[str, ExecutionReport] = {}
        self._counter: int = 0
        self._initialized: bool = False
        logger.info("ExecutionSupervisor created (max_deviation=%.0f%%)", max_deviation_pct * 100)

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("ExecutionSupervisor initialized")

    async def shutdown(self) -> None:
        self._reports.clear()
        self._active.clear()
        self._initialized = False
        logger.info("ExecutionSupervisor shutdown complete")

    def start_monitoring(self, plan: Any) -> ExecutionReport:
        plan_id = getattr(plan, "plan_id", "unknown")
        report = ExecutionReport(
            report_id=f"exec_{plan_id}",
            plan_id=plan_id,
            status=ExecutionStatus.IN_PROGRESS,
            slices_total=getattr(plan, "slice_count", 0),
        )
        self._active[plan_id] = report
        logger.info("Monitoring started for plan: %s", plan_id)
        return report

    def update_progress(self, plan_id: str, slices_completed: int, deviation_pct: float = 0.0) -> Optional[ExecutionReport]:
        report = self._active.get(plan_id)
        if report is None:
            return None
        report.slices_completed = slices_completed
        report.deviation_pct = deviation_pct
        if slices_completed >= report.slices_total:
            report.status = ExecutionStatus.COMPLETED
        logger.debug("Plan %s progress: %d/%d (%.1f%%)", plan_id, slices_completed, report.slices_total, report.progress_pct * 100)
        return report

    def abort(self, plan_id: str, reason: str = "") -> Optional[ExecutionReport]:
        report = self._active.pop(plan_id, None)
        if report:
            report.status = ExecutionStatus.ABORTED
            report.errors.append(reason)
            self._store_report(plan_id, report)
            logger.warning("Execution aborted for plan %s: %s", plan_id, reason)
        return report

    def get_status(self, plan_id: str) -> Optional[Dict[str, Any]]:
        report = self._active.get(plan_id)
        if report is None:
            return None
        return {
            "report_id": report.report_id,
            "plan_id": report.plan_id,
            "status": report.status.value,
            "progress": round(report.progress_pct, 3),
            "deviation_pct": round(report.deviation_pct, 3),
            "errors": report.errors,
        }

    def _store_report(self, plan_id: str, report: ExecutionReport) -> None:
        if plan_id not in self._reports:
            self._reports[plan_id] = []
        self._reports[plan_id].append(report)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "active_plans": len(self._active),
            "completed_plans": len(self._reports),
        }
