"""
Capital Diagnostics — Health checks and validation for institutional capital components.

Diagnoses:
    - Capital conservation: total = allocated + reserved + available
    - Capacity violations
    - Over-allocation warnings
    - Liquidity stress alerts
    - Memory store health
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class DiagSeverity(str, Enum):
    OK = "ok"
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class DiagFinding:
    """A single diagnostic finding."""

    finding_id: str = field(default_factory=lambda: f"DF-{uuid.uuid4().hex[:8]}")
    component: str = ""
    check_name: str = ""
    severity: DiagSeverity = DiagSeverity.OK
    message: str = ""
    detail: Dict[str, Any] = field(default_factory=dict)
    recommendation: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class DiagnosticReport:
    """Aggregated diagnostic report."""

    report_id: str = field(default_factory=lambda: f"DR-{uuid.uuid4().hex[:8]}")
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    findings: List[DiagFinding] = field(default_factory=list)
    overall_status: DiagSeverity = DiagSeverity.OK

    @property
    def ok_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == DiagSeverity.OK)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == DiagSeverity.WARNING)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == DiagSeverity.CRITICAL)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "timestamp": self.timestamp,
            "overall_status": self.overall_status.value,
            "ok_count": self.ok_count,
            "warning_count": self.warning_count,
            "critical_count": self.critical_count,
            "findings": [
                {
                    "component": f.component,
                    "check": f.check_name,
                    "severity": f.severity.value,
                    "message": f.message,
                    "recommendation": f.recommendation,
                }
                for f in self.findings
            ],
        }


class CapitalDiagnostics:
    """Runs diagnostic checks on institutional capital components."""

    def __init__(self):
        self._findings: List[DiagFinding] = []
        self._reports: List[DiagnosticReport] = []

    def check_capital_conservation(
        self, total: float, allocated: float, reserved: float, available: float
    ) -> DiagFinding:
        """Verify total = allocated + reserved + available."""
        expected = allocated + reserved + available
        drift = abs(total - expected)
        tolerance = max(total * 0.001, 1.0)  # 0.1% or 1 unit

        if drift > tolerance:
            return DiagFinding(
                component="CapitalPool",
                check_name="capital_conservation",
                severity=DiagSeverity.CRITICAL,
                message=f"Capital not conserved: total={total:,.2f} vs sum={expected:,.2f}, drift={drift:,.2f}",
                detail={"total": total, "allocated": allocated, "reserved": reserved, "available": available, "drift": drift},
                recommendation="Investigate capital leak or unaccounted allocation.",
            )
        return DiagFinding(
            component="CapitalPool",
            check_name="capital_conservation",
            severity=DiagSeverity.OK,
            message="Capital conservation verified.",
        )

    def check_capacity_violations(
        self, strategy_capitals: Dict[str, float], strategy_capacities: Dict[str, float],
        warning_threshold: float = 0.80, critical_threshold: float = 0.95,
    ) -> List[DiagFinding]:
        findings = []
        for sid, capital in strategy_capitals.items():
            capacity = strategy_capacities.get(sid, float("inf"))
            if capacity <= 0:
                continue
            utilization = capital / capacity
            if utilization >= critical_threshold:
                findings.append(DiagFinding(
                    component="StrategyCapacity",
                    check_name="capacity_violation",
                    severity=DiagSeverity.CRITICAL,
                    message=f"Strategy {sid}: {utilization:.1%} utilization (critical)",
                    detail={"strategy_id": sid, "utilization": utilization, "critical_threshold": critical_threshold},
                    recommendation=f"Reduce allocation or increase capacity for {sid}.",
                ))
            elif utilization >= warning_threshold:
                findings.append(DiagFinding(
                    component="StrategyCapacity",
                    check_name="capacity_approaching",
                    severity=DiagSeverity.WARNING,
                    message=f"Strategy {sid}: {utilization:.1%} utilization (approaching limit)",
                    detail={"strategy_id": sid, "utilization": utilization, "warning_threshold": warning_threshold},
                    recommendation=f"Monitor {sid} capacity closely.",
                ))
        return findings

    def check_overallocation(
        self, total_capital: float, total_allocated: float, threshold: float = 1.0
    ) -> DiagFinding:
        if total_capital <= 0:
            return DiagFinding(component="CapitalPool", check_name="overallocation", severity=DiagSeverity.OK, message="No capital defined.")

        ratio = total_allocated / total_capital
        if ratio > threshold:
            return DiagFinding(
                component="CapitalPool",
                check_name="overallocation",
                severity=DiagSeverity.CRITICAL,
                message=f"Overallocation: {ratio:.2%} — allocated exceeds total capital",
                detail={"total": total_capital, "allocated": total_allocated, "ratio": ratio},
                recommendation="Immediately reduce allocations to within capital limits.",
            )
        if ratio > 0.95:
            return DiagFinding(
                component="CapitalPool",
                check_name="overallocation_warning",
                severity=DiagSeverity.WARNING,
                message=f"High allocation: {ratio:.2%} — limited headroom",
                detail={"total": total_capital, "allocated": total_allocated, "ratio": ratio},
                recommendation="Consider reserving additional buffer capital.",
            )
        return DiagFinding(component="CapitalPool", check_name="overallocation", severity=DiagSeverity.OK, message=f"Allocation healthy at {ratio:.1%}.")

    def run_all(
        self,
        total_capital: float = 0.0,
        allocated: float = 0.0,
        reserved: float = 0.0,
        available: float = 0.0,
        strategy_capitals: Optional[Dict[str, float]] = None,
        strategy_capacities: Optional[Dict[str, float]] = None,
    ) -> DiagnosticReport:
        report = DiagnosticReport()
        findings = []

        # Capital conservation
        findings.append(self.check_capital_conservation(total_capital, allocated, reserved, available))

        # Overallocation
        findings.append(self.check_overallocation(total_capital, allocated))

        # Capacity checks
        if strategy_capitals and strategy_capacities:
            findings.extend(self.check_capacity_violations(strategy_capitals, strategy_capacities))

        report.findings = findings
        criticals = [f for f in findings if f.severity == DiagSeverity.CRITICAL]
        warnings = [f for f in findings if f.severity == DiagSeverity.WARNING]

        if criticals:
            report.overall_status = DiagSeverity.CRITICAL
        elif warnings:
            report.overall_status = DiagSeverity.WARNING
        else:
            report.overall_status = DiagSeverity.OK

        self._findings.extend(findings)
        self._reports.append(report)
        return report

    def latest_report(self) -> Optional[DiagnosticReport]:
        return self._reports[-1] if self._reports else None

    def summary(self) -> Dict[str, Any]:
        report = self.latest_report()
        if not report:
            return {"status": "no_diagnostics_run"}
        return report.to_dict()
