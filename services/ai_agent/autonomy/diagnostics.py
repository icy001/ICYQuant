"""Autonomy Diagnostics — performance analysis and health insights for autonomous workflows.

Provides:
    - Workflow success/failure rates
    - Stage-level latency analysis
    - Approval rate tracking
    - Learning pipeline effectiveness
    - Safety decision distribution
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class DiagnosticReport:
    workflow_success_rate: float = 1.0
    workflow_count: int = 0
    approval_rate: float = 1.0
    rejection_rate: float = 0.0
    avg_confidence: float = 0.0
    issues: List[Dict[str, Any]] = field(default_factory=list)


class AutonomyDiagnostics:
    """Performance diagnostics for the autonomous research subsystem.

    Usage:
        diag = AutonomyDiagnostics()
        diag.record_workflow_success()
        report = diag.generate_report()
    """

    def __init__(self) -> None:
        self._workflow_success: int = 0
        self._workflow_failure: int = 0
        self._approvals_auto: int = 0
        self._approvals_human: int = 0
        self._rejections: int = 0
        self._confidence_values: List[float] = []
        self._initialized: bool = False
        logger.info("AutonomyDiagnostics created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("AutonomyDiagnostics initialized")

    async def shutdown(self) -> None:
        self._initialized = False
        logger.info("AutonomyDiagnostics shutdown complete")

    def record_workflow_success(self) -> None:
        self._workflow_success += 1

    def record_workflow_failure(self) -> None:
        self._workflow_failure += 1

    def record_auto_approval(self) -> None:
        self._approvals_auto += 1

    def record_human_approval(self) -> None:
        self._approvals_human += 1

    def record_rejection(self) -> None:
        self._rejections += 1

    def record_confidence(self, value: float) -> None:
        self._confidence_values.append(value)

    def generate_report(self) -> DiagnosticReport:
        total = self._workflow_success + self._workflow_failure
        success_rate = self._workflow_success / total if total > 0 else 1.0
        total_approvals = self._approvals_auto + self._approvals_human + self._rejections
        approval_rate = (self._approvals_auto + self._approvals_human) / total_approvals if total_approvals > 0 else 1.0
        avg_confidence = sum(self._confidence_values) / len(self._confidence_values) if self._confidence_values else 0.0

        issues: List[Dict[str, Any]] = []
        if success_rate < 0.8:
            issues.append({"severity": "WARNING", "type": "low_success_rate", "detail": f"Workflow success rate {success_rate:.1%} < 80%"})

        return DiagnosticReport(
            workflow_success_rate=round(success_rate, 4),
            workflow_count=total,
            approval_rate=round(approval_rate, 4),
            rejection_rate=round(self._rejections / total_approvals if total_approvals > 0 else 0.0, 4),
            avg_confidence=round(avg_confidence, 4),
            issues=issues,
        )

    def get_summary(self) -> Dict[str, Any]:
        report = self.generate_report()
        return {
            "workflow_success_rate": report.workflow_success_rate,
            "approval_rate": report.approval_rate,
            "avg_confidence": report.avg_confidence,
            "issues": len(report.issues),
        }

    def reset(self) -> None:
        self._workflow_success = 0
        self._workflow_failure = 0
        self._approvals_auto = 0
        self._approvals_human = 0
        self._rejections = 0
        self._confidence_values.clear()
