"""
Portfolio Diagnostics — Health diagnostics for portfolio subsystems.

Provides structured diagnostic checks for all portfolio risk
subsystems with status reporting and issue detection.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DiagnosticStatus(str, Enum):
    """Diagnostic check status."""
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"


@dataclass
class DiagnosticCheck:
    """Result of a single diagnostic check."""
    name: str
    status: DiagnosticStatus
    message: str = ""
    detail: str = ""
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DiagnosticReport:
    """Aggregate diagnostic report for the portfolio platform."""
    overall_status: DiagnosticStatus = DiagnosticStatus.PASS
    checks: list[DiagnosticCheck] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_checks: int = 0
    passed: int = 0
    warnings: int = 0
    failed: int = 0
    total_duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_status": self.overall_status.value,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message,
                    "detail": c.detail,
                    "duration_ms": c.duration_ms,
                }
                for c in self.checks
            ],
            "generated_at": self.generated_at.isoformat(),
            "total_checks": self.total_checks,
            "passed": self.passed,
            "warnings": self.warnings,
            "failed": self.failed,
            "total_duration_ms": self.total_duration_ms,
        }


class PortfolioDiagnostics:
    """
    Health diagnostics for the portfolio risk platform.

    Runs diagnostic checks across all portfolio subsystems and
    generates a structured diagnostic report for operational
    monitoring.

    Usage::

        diag = PortfolioDiagnostics()
        await diag.initialize()

        # Register subsystems
        diag.register_subsystem("pnl_engine", pnl_engine)
        diag.register_subsystem("exposure_engine", exposure_engine)

        report = await diag.run_diagnostics()
    """

    def __init__(self) -> None:
        self._subsystems: dict[str, Any] = {}
        self._custom_checks: dict[str, callable] = {}
        self._last_report: Optional[DiagnosticReport] = None
        self._initialized = False

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize diagnostics."""
        self._initialized = True
        logger.info("PortfolioDiagnostics initialized.")

    # ---- Registration ----

    def register_subsystem(self, name: str, instance: Any) -> None:
        """Register a subsystem for diagnostic checking."""
        self._subsystems[name] = instance
        logger.debug(f"Diagnostics subsystem registered: {name}")

    def register_check(self, name: str, check_fn: callable) -> None:
        """Register a custom diagnostic check function."""
        self._custom_checks[name] = check_fn

    # ---- Core API ----

    async def run_diagnostics(self) -> DiagnosticReport:
        """
        Run all diagnostic checks.

        Checks each registered subsystem's health_check() method
        and runs any custom check functions. Returns a comprehensive
        DiagnosticReport.
        """
        import time
        t_start = time.perf_counter()

        checks: list[DiagnosticCheck] = []

        # Check each subsystem
        for name, subsystem in self._subsystems.items():
            check = await self._check_subsystem(name, subsystem)
            checks.append(check)

        # Run custom checks
        for name, check_fn in self._custom_checks.items():
            try:
                result = await check_fn() if asyncio.iscoroutinefunction(check_fn) else check_fn()
                checks.append(DiagnosticCheck(
                    name=name,
                    status=DiagnosticStatus.PASS if result else DiagnosticStatus.WARN,
                    message=str(result),
                ))
            except Exception as e:
                checks.append(DiagnosticCheck(
                    name=name,
                    status=DiagnosticStatus.FAIL,
                    message=f"Custom check failed: {e}",
                ))

        # Aggregate
        total = len(checks)
        passed = sum(1 for c in checks if c.status == DiagnosticStatus.PASS)
        warnings = sum(1 for c in checks if c.status == DiagnosticStatus.WARN)
        failed = sum(1 for c in checks if c.status == DiagnosticStatus.FAIL)

        if failed > 0:
            overall = DiagnosticStatus.FAIL
        elif warnings > 0:
            overall = DiagnosticStatus.WARN
        else:
            overall = DiagnosticStatus.PASS

        total_duration = (time.perf_counter() - t_start) * 1000

        report = DiagnosticReport(
            overall_status=overall,
            checks=checks,
            total_checks=total,
            passed=passed,
            warnings=warnings,
            failed=failed,
            total_duration_ms=total_duration,
        )

        self._last_report = report

        logger.info(
            f"Diagnostics complete: {overall.value} "
            f"(passed={passed}, warn={warnings}, fail={failed}, "
            f"time={total_duration:.1f}ms)"
        )

        return report

    async def quick_check(self) -> dict[str, Any]:
        """Fast diagnostic check returning only overall status."""
        report = await self.run_diagnostics()
        return {
            "status": report.overall_status.value,
            "failed": report.failed,
            "warnings": report.warnings,
        }

    # ---- Query ----

    def get_last_report(self) -> Optional[DiagnosticReport]:
        """Get the most recent diagnostic report."""
        return self._last_report

    # ---- Internal ----

    async def _check_subsystem(self, name: str, subsystem: Any) -> DiagnosticCheck:
        """Run diagnostic check on a single subsystem."""
        import time
        t_start = time.perf_counter()

        try:
            if hasattr(subsystem, "health_check"):
                result = await subsystem.health_check()
                status_str = result.get("status", "unknown")

                if status_str in ("healthy", "running", "HEALTHY"):
                    status = DiagnosticStatus.PASS
                    message = f"{name} is healthy"
                elif status_str in ("degraded", "DEGRADED"):
                    status = DiagnosticStatus.WARN
                    message = f"{name} is degraded"
                elif status_str in ("not_initialized",):
                    status = DiagnosticStatus.WARN
                    message = f"{name} is not initialized"
                else:
                    status = DiagnosticStatus.FAIL
                    message = f"{name} status: {status_str}"

                return DiagnosticCheck(
                    name=name,
                    status=status,
                    message=message,
                    detail=str(result),
                    duration_ms=(time.perf_counter() - t_start) * 1000,
                    metadata=result,
                )
            else:
                return DiagnosticCheck(
                    name=name,
                    status=DiagnosticStatus.WARN,
                    message=f"{name} has no health_check method",
                    duration_ms=(time.perf_counter() - t_start) * 1000,
                )
        except Exception as e:
            return DiagnosticCheck(
                name=name,
                status=DiagnosticStatus.FAIL,
                message=f"Check failed: {e}",
                duration_ms=(time.perf_counter() - t_start) * 1000,
            )
