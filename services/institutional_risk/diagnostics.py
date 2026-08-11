"""RiskDiagnostics — risk subsystem health diagnostics.

Runs diagnostic checks on the risk subsystem to verify
all components are functioning correctly.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class DiagnosticStatus(Enum):
    PASS = auto()
    WARN = auto()
    FAIL = auto()


@dataclass
class DiagnosticCheck:
    """A single diagnostic check result."""

    name: str
    status: DiagnosticStatus
    message: str = ""
    value: Optional[float] = None
    threshold: Optional[float] = None
    timestamp: float = 0.0
    latency_ms: float = 0.0


@dataclass
class DiagnosticReport:
    """Full diagnostic report."""

    overall: DiagnosticStatus = DiagnosticStatus.PASS
    checks: List[DiagnosticCheck] = field(default_factory=list)
    passed: int = 0
    warnings: int = 0
    failures: int = 0
    timestamp: float = 0.0
    total_latency_ms: float = 0.0


class RiskDiagnostics:
    """Risk subsystem diagnostics.

    Checks:
    1. Risk engine liveness
    2. VaR computation validity
    3. Stress engine availability
    4. Survival scoring consistency
    5. Risk budget logic
    6. Guard chain completeness
    7. Memory/telemetry integrity

    Usage::

        diag = RiskDiagnostics()
        report = diag.run(engine_snapshot={...})
        if report.overall != DiagnosticStatus.PASS:
            print(f"WARNING: {report.failures} checks failed")
    """

    def run(
        self,
        engine_snapshot: Optional[Dict[str, Any]] = None,
    ) -> DiagnosticReport:
        """Run all diagnostic checks.

        Args:
            engine_snapshot: current risk engine state snapshot
        """
        start = time.time()
        report = DiagnosticReport(timestamp=start)
        snapshot = engine_snapshot or {}

        # Check 1: risk engine liveness
        report.checks.append(self._check_liveness(snapshot))

        # Check 2: VaR consistency
        report.checks.append(self._check_var_consistency(snapshot))

        # Check 3: survival score bounds
        report.checks.append(self._check_survival_bounds(snapshot))

        # Check 4: risk budget consistency
        report.checks.append(self._check_risk_budget(snapshot))

        # Check 5: drawdown tracking
        report.checks.append(self._check_drawdown(snapshot))

        # Check 6: stress engine
        report.checks.append(self._check_stress_availability(snapshot))

        # Check 7: guard chain
        report.checks.append(self._check_guard_chain(snapshot))

        # aggregate
        for check in report.checks:
            if check.status == DiagnosticStatus.PASS:
                report.passed += 1
            elif check.status == DiagnosticStatus.WARN:
                report.warnings += 1
            else:
                report.failures += 1

        if report.failures > 0:
            report.overall = DiagnosticStatus.FAIL
        elif report.warnings > 0:
            report.overall = DiagnosticStatus.WARN

        report.total_latency_ms = (time.time() - start) * 1000
        return report

    def _check_liveness(self, snapshot: Dict[str, Any]) -> DiagnosticCheck:
        """Check that risk engine is producing snapshots."""
        latest_ts = snapshot.get("latest_snapshot_ts", 0)
        now = time.time()
        age = now - latest_ts if latest_ts > 0 else 999

        if age < 5:
            return DiagnosticCheck(
                name="engine_liveness",
                status=DiagnosticStatus.PASS,
                message=f"Last snapshot {age:.1f}s ago",
                value=age,
                threshold=5.0,
            )
        elif age < 30:
            return DiagnosticCheck(
                name="engine_liveness",
                status=DiagnosticStatus.WARN,
                message=f"Last snapshot {age:.0f}s ago — may be stalled",
                value=age,
                threshold=5.0,
            )
        else:
            return DiagnosticCheck(
                name="engine_liveness",
                status=DiagnosticStatus.FAIL,
                message=f"No recent snapshots ({age:.0f}s)",
                value=age,
                threshold=5.0,
            )

    def _check_var_consistency(self, snapshot: Dict[str, Any]) -> DiagnosticCheck:
        """Check VaR metrics are consistent."""
        var_95 = snapshot.get("var_95", 0.0)
        var_99 = snapshot.get("var_99", 0.0)

        if var_95 <= 0 or var_99 <= 0:
            return DiagnosticCheck(
                name="var_values",
                status=DiagnosticStatus.WARN,
                message="VaR values are zero or negative",
            )

        if var_99 < var_95:
            return DiagnosticCheck(
                name="var_consistency",
                status=DiagnosticStatus.FAIL,
                message=f"VaR 99% ({var_99}) < VaR 95% ({var_95})",
            )

        return DiagnosticCheck(
            name="var_consistency",
            status=DiagnosticStatus.PASS,
            message=f"VaR 95%={var_95:.0f}, 99%={var_99:.0f}",
        )

    def _check_survival_bounds(self, snapshot: Dict[str, Any]) -> DiagnosticCheck:
        """Check survival score is within [0, 100]."""
        score = snapshot.get("survival_score", -1)

        if score < 0 or score > 100:
            return DiagnosticCheck(
                name="survival_bounds",
                status=DiagnosticStatus.FAIL,
                message=f"Survival score {score} out of bounds [0,100]",
                value=score,
            )

        if score < 30:
            return DiagnosticCheck(
                name="survival_score",
                status=DiagnosticStatus.WARN,
                message=f"Survival score critically low: {score:.0f}/100",
                value=score,
                threshold=30.0,
            )

        return DiagnosticCheck(
            name="survival_score",
            status=DiagnosticStatus.PASS,
            message=f"Survival: {score:.0f}/100",
            value=score,
        )

    def _check_risk_budget(self, snapshot: Dict[str, Any]) -> DiagnosticCheck:
        """Check risk budget consistency."""
        total = snapshot.get("risk_budget_total", 0.0)
        used = snapshot.get("risk_budget_used", 0.0)

        if total <= 0:
            return DiagnosticCheck(
                name="risk_budget",
                status=DiagnosticStatus.WARN,
                message="Risk budget not configured",
            )

        utilization = (used / total * 100) if total > 0 else 0
        if utilization > 100:
            return DiagnosticCheck(
                name="risk_budget",
                status=DiagnosticStatus.FAIL,
                message=f"Risk budget exceeded: {utilization:.0f}%",
                value=utilization,
                threshold=100.0,
            )

        return DiagnosticCheck(
            name="risk_budget",
            status=DiagnosticStatus.PASS,
            message=f"Budget: {utilization:.0f}% used",
            value=utilization,
        )

    def _check_drawdown(self, snapshot: Dict[str, Any]) -> DiagnosticCheck:
        """Check drawdown tracking."""
        dd = snapshot.get("drawdown_pct", 0.0)
        max_dd = snapshot.get("max_drawdown_pct", 0.0)

        if max_dd < dd:
            return DiagnosticCheck(
                name="drawdown",
                status=DiagnosticStatus.FAIL,
                message=f"Max DD ({max_dd:.1f}%) < current DD ({dd:.1f}%)",
            )

        if dd > 30:
            return DiagnosticCheck(
                name="drawdown",
                status=DiagnosticStatus.WARN,
                message=f"Drawdown critical: {dd:.1f}%",
                value=dd,
                threshold=30.0,
            )

        return DiagnosticCheck(
            name="drawdown",
            status=DiagnosticStatus.PASS,
            message=f"Drawdown: {dd:.1f}% (max: {max_dd:.1f}%)",
        )

    def _check_stress_availability(self, snapshot: Dict[str, Any]) -> DiagnosticCheck:
        """Check stress engine is available."""
        stress_runs = snapshot.get("stress_tests_run", -1)
        if stress_runs < 0:
            return DiagnosticCheck(
                name="stress_engine",
                status=DiagnosticStatus.WARN,
                message="No stress tests have been run",
            )
        return DiagnosticCheck(
            name="stress_engine",
            status=DiagnosticStatus.PASS,
            message=f"{stress_runs} stress tests run",
        )

    def _check_guard_chain(self, snapshot: Dict[str, Any]) -> DiagnosticCheck:
        """Check guard chain is active."""
        guards = snapshot.get("active_guards", 0)
        if guards < 3:  # risk, survival, stress
            return DiagnosticCheck(
                name="guard_chain",
                status=DiagnosticStatus.WARN,
                message=f"Only {guards}/3 guards active",
                value=float(guards),
                threshold=3.0,
            )
        return DiagnosticCheck(
            name="guard_chain",
            status=DiagnosticStatus.PASS,
            message="All 3 guards active",
            value=float(guards),
        )
