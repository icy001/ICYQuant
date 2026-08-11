"""Allocation Diagnostics — health checks and anomaly detection.

Checks for:
- Capital conservation violations
- Allocation drift from targets
- Constraint violations
- Model prediction degradation
- Guard override patterns
- System health indicators
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class DiagnosticCheck:
    """A single diagnostic check result."""
    check_name: str
    status: str = "OK"  # OK, WARNING, ERROR
    value: Any = None
    expected: Any = None
    message: str = ""
    recommendation: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DiagnosticReport:
    """Complete diagnostic report."""
    checks: List[DiagnosticCheck] = field(default_factory=list)
    total_checks: int = 0
    passed: int = 0
    warnings: int = 0
    errors: int = 0
    overall_status: str = "HEALTHY"
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def summarize(self) -> str:
        lines = [
            f"DiagnosticReport [{self.overall_status}]",
            f"  Passed: {self.passed}/{self.total_checks}",
            f"  Warnings: {self.warnings}",
            f"  Errors: {self.errors}",
        ]
        for c in self.checks:
            if c.status != "OK":
                lines.append(f"  [{c.status}] {c.check_name}: {c.message}")
        return "\n".join(lines)


class AllocationDiagnostics:
    """Diagnostic system for autonomous allocation.

    Periodic health checks to detect:
    - Capital leaks (total allocations ≠ capital)
    - Drift beyond thresholds
    - Constraint soft-violations accumulating
    - Prediction error trends (model degradation)
    - Guard override frequency
    """

    def __init__(self):
        self._checks: List[DiagnosticCheck] = []
        self._last_report: Optional[DiagnosticReport] = None

    def run_diagnostics(self,
                        total_capital: float = 0.0,
                        total_allocated: float = 0.0,
                        reserve: float = 0.0,
                        buffer: float = 0.0,
                        weights: Optional[Dict[str, float]] = None,
                        target_weights: Optional[Dict[str, float]] = None,
                        guard_rejections: int = 0,
                        guard_total: int = 0,
                        prediction_errors: Optional[Dict[str, float]] = None,
                        feedback_events: int = 0) -> DiagnosticReport:
        """Run all diagnostic checks."""
        weights = weights or {}
        target_weights = target_weights or {}
        prediction_errors = prediction_errors or {}
        report = DiagnosticReport()

        checks = []

        # Check 1: Capital conservation
        total_implied = total_allocated + reserve + buffer
        capital_diff = abs(total_capital - total_implied)
        checks.append(DiagnosticCheck(
            check_name="capital_conservation",
            status="OK" if capital_diff < 1.0 else "ERROR",
            value=total_implied,
            expected=total_capital,
            message=f"Capital {total_capital:,.0f} vs implied {total_implied:,.0f} (diff={capital_diff:,.0f})",
        ))

        # Check 2: Weight sum
        weight_sum = sum(weights.values())
        checks.append(DiagnosticCheck(
            check_name="weight_sum",
            status="OK" if abs(weight_sum - 1.0) < 0.01 else "WARNING",
            value=weight_sum,
            expected=1.0,
            message=f"Weight sum = {weight_sum:.4f}",
        ))

        # Check 3: Weight drift
        max_drift = 0.0
        for sid, weight in weights.items():
            target = target_weights.get(sid, weight)
            drift = abs(weight - target)
            max_drift = max(max_drift, drift)

        drift_status = "OK" if max_drift < 0.03 else ("WARNING" if max_drift < 0.05 else "ERROR")
        checks.append(DiagnosticCheck(
            check_name="weight_drift",
            status=drift_status,
            value=max_drift,
            expected=0.03,
            message=f"Max weight drift = {max_drift:.4f}",
        ))

        # Check 4: Guard violations rate
        guard_rate = guard_rejections / max(1, guard_total)
        guard_status = "OK" if guard_rate < 0.10 else ("WARNING" if guard_rate < 0.25 else "ERROR")
        checks.append(DiagnosticCheck(
            check_name="guard_rejection_rate",
            status=guard_status,
            value=guard_rate,
            expected=0.10,
            message=f"Guard rejection rate = {guard_rate:.1%}",
        ))

        # Check 5: Prediction error magnitude
        if prediction_errors:
            max_error = max(abs(e) for e in prediction_errors.values())
            error_status = "OK" if max_error < 0.20 else ("WARNING" if max_error < 0.40 else "ERROR")
            checks.append(DiagnosticCheck(
                check_name="prediction_error_max",
                status=error_status,
                value=max_error,
                expected=0.20,
                message=f"Max prediction error = {max_error:.2%}",
                recommendation="Consider model recalibration" if max_error > 0.30 else "",
            ))

        # Check 6: Feedback loop health
        feedback_status = "OK" if feedback_events > 0 else "WARNING"
        checks.append(DiagnosticCheck(
            check_name="feedback_loop_active",
            status=feedback_status,
            value=feedback_events,
            expected=">0",
            message=f"Feedback events: {feedback_events}",
            recommendation="Ensure feedback loop is running" if feedback_events == 0 else "",
        ))

        # Check 7: Capital buffer adequacy
        buffer_ratio = buffer / max(1, total_capital)
        buffer_status = "OK" if buffer_ratio >= 0.03 else ("WARNING" if buffer_ratio >= 0.01 else "ERROR")
        checks.append(DiagnosticCheck(
            check_name="buffer_adequacy",
            status=buffer_status,
            value=buffer_ratio,
            expected=0.03,
            message=f"Buffer ratio = {buffer_ratio:.1%}",
            recommendation="Increase capital buffer" if buffer_ratio < 0.03 else "",
        ))

        report.checks = checks
        report.total_checks = len(checks)
        report.passed = sum(1 for c in checks if c.status == "OK")
        report.warnings = sum(1 for c in checks if c.status == "WARNING")
        report.errors = sum(1 for c in checks if c.status == "ERROR")

        if report.errors > 0:
            report.overall_status = "UNHEALTHY"
        elif report.warnings > 0:
            report.overall_status = "DEGRADED"
        else:
            report.overall_status = "HEALTHY"

        self._last_report = report
        return report

    def get_last_report(self) -> Optional[DiagnosticReport]:
        """Get the most recent diagnostic report."""
        return self._last_report
