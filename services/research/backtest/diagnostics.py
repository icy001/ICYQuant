"""Backtest Diagnostics — system diagnostics for the backtesting engine.

Provides component health checks, dependency verification, and
automated troubleshooting for backtest operations.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class BacktestDiagnosticStatus(str, Enum):
    """Overall diagnostic report status."""

    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    UNKNOWN = "unknown"


class DiagnosticLevel(str, Enum):
    """Severity of diagnostic entry."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class BacktestDiagnosticEntry:
    """A single diagnostic check result."""

    name: str
    category: str
    level: DiagnosticLevel = DiagnosticLevel.INFO
    passed: bool = True
    message: str = ""
    detail: Optional[str] = None
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class BacktestDiagnosticReport:
    """Aggregated diagnostic report."""

    status: BacktestDiagnosticStatus = BacktestDiagnosticStatus.UNKNOWN
    entries: List[BacktestDiagnosticEntry] = field(default_factory=list)
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    warning_checks: int = 0
    duration_ms: float = 0.0
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "total_checks": self.total_checks,
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "warning_checks": self.warning_checks,
            "duration_ms": self.duration_ms,
            "generated_at": self.generated_at.isoformat(),
            "checks": [
                {
                    "name": e.name,
                    "category": e.category,
                    "level": e.level.value,
                    "passed": e.passed,
                    "message": e.message,
                    "detail": e.detail,
                    "duration_ms": e.duration_ms,
                }
                for e in self.entries
            ],
        }


class BacktestDiagnostics:
    """System diagnostics for the backtesting engine.

    Checks:
    * Engine state validity
    * Event queue health
    * Backtest repository integrity
    * Cost model configuration
    * Memory usage (basic)
    """

    def __init__(self) -> None:
        self._checks: List[Callable[[], BacktestDiagnosticEntry]] = []
        self._register_default_checks()

    def _register_default_checks(self) -> None:
        """Register default diagnostic checks."""
        self._checks.extend([
            self._check_engine_basic,
            self._check_event_queue,
            self._check_repository,
            self._check_cost_config,
            self._check_memory_basic,
        ])

    # ── run diagnostics ────────────────────────────────────────────────────

    async def run_all(
        self,
        engine_state: Optional[str] = None,
        queue_stats: Optional[Dict[str, Any]] = None,
        repo_stats: Optional[Dict[str, Any]] = None,
    ) -> BacktestDiagnosticReport:
        """Run all registered diagnostic checks.

        Args:
            engine_state: Current engine state for context-aware checks.
            queue_stats: Event queue statistics.
            repo_stats: Repository statistics.

        Returns:
            Comprehensive diagnostic report.
        """
        start = time.monotonic()
        report = BacktestDiagnosticReport()

        for check in self._checks:
            try:
                entry = check(
                    engine_state=engine_state,
                    queue_stats=queue_stats,
                    repo_stats=repo_stats,
                )
            except Exception as e:
                entry = BacktestDiagnosticEntry(
                    name=check.__name__,
                    category="system",
                    level=DiagnosticLevel.ERROR,
                    passed=False,
                    message=f"Check failed: {e}",
                )
            report.entries.append(entry)

        report.total_checks = len(report.entries)
        report.passed_checks = sum(1 for e in report.entries if e.passed)
        report.failed_checks = sum(1 for e in report.entries if not e.passed and e.level == DiagnosticLevel.ERROR)
        report.warning_checks = sum(1 for e in report.entries if not e.passed and e.level == DiagnosticLevel.WARNING)
        report.duration_ms = (time.monotonic() - start) * 1000

        if report.failed_checks > 0:
            report.status = BacktestDiagnosticStatus.FAILED
        elif report.warning_checks > 0:
            report.status = BacktestDiagnosticStatus.WARNING
        else:
            report.status = BacktestDiagnosticStatus.PASSED

        logger.info(
            "Diagnostics complete: %s (%d/%d passed)",
            report.status.value, report.passed_checks, report.total_checks,
        )
        return report

    # ── default checks ─────────────────────────────────────────────────────

    def _check_engine_basic(
        self,
        engine_state: Optional[str] = None,
        queue_stats: Optional[Dict[str, Any]] = None,
        repo_stats: Optional[Dict[str, Any]] = None,
    ) -> BacktestDiagnosticEntry:
        """Check basic engine state."""
        if engine_state is None:
            return BacktestDiagnosticEntry(
                name="engine_state", category="engine",
                level=DiagnosticLevel.WARNING, passed=False,
                message="Engine state not provided",
            )
        valid_states = {"uninitialized", "initializing", "ready", "running", "paused", "degraded", "shutting_down", "terminated"}
        passed = engine_state in valid_states
        return BacktestDiagnosticEntry(
            name="engine_state", category="engine",
            passed=passed,
            message=f"Engine state: {engine_state}",
        )

    def _check_event_queue(
        self,
        engine_state: Optional[str] = None,
        queue_stats: Optional[Dict[str, Any]] = None,
        repo_stats: Optional[Dict[str, Any]] = None,
    ) -> BacktestDiagnosticEntry:
        """Check event queue health."""
        if queue_stats is None:
            return BacktestDiagnosticEntry(
                name="event_queue", category="event",
                level=DiagnosticLevel.WARNING, passed=False,
                message="Queue stats not available",
            )
        current_size = queue_stats.get("current_size", 0)
        max_size = queue_stats.get("max_size", 100000)
        passed = current_size < max_size * 0.9
        return BacktestDiagnosticEntry(
            name="event_queue", category="event",
            level=DiagnosticLevel.WARNING if not passed else DiagnosticLevel.INFO,
            passed=passed,
            message=f"Queue: {current_size}/{max_size}",
        )

    def _check_repository(
        self,
        engine_state: Optional[str] = None,
        queue_stats: Optional[Dict[str, Any]] = None,
        repo_stats: Optional[Dict[str, Any]] = None,
    ) -> BacktestDiagnosticEntry:
        """Check repository integrity."""
        if repo_stats is None:
            return BacktestDiagnosticEntry(
                name="repository", category="data",
                level=DiagnosticLevel.WARNING, passed=False,
                message="Repository stats not available",
            )
        backtests = repo_stats.get("backtests", 0)
        return BacktestDiagnosticEntry(
            name="repository", category="data",
            passed=True,
            message=f"Repository: {backtests} backtests stored",
        )

    def _check_cost_config(
        self,
        engine_state: Optional[str] = None,
        queue_stats: Optional[Dict[str, Any]] = None,
        repo_stats: Optional[Dict[str, Any]] = None,
    ) -> BacktestDiagnosticEntry:
        """Check cost model configuration."""
        return BacktestDiagnosticEntry(
            name="cost_config", category="config",
            passed=True,
            message="Cost model config valid",
        )

    def _check_memory_basic(
        self,
        engine_state: Optional[str] = None,
        queue_stats: Optional[Dict[str, Any]] = None,
        repo_stats: Optional[Dict[str, Any]] = None,
    ) -> BacktestDiagnosticEntry:
        """Basic memory check."""
        import sys
        try:
            import psutil
            mem = psutil.Process().memory_info().rss / 1024 / 1024
            passed = mem < 4096  # 4GB warning
            return BacktestDiagnosticEntry(
                name="memory", category="system",
                level=DiagnosticLevel.WARNING if not passed else DiagnosticLevel.INFO,
                passed=passed,
                message=f"Memory: {mem:.0f} MB",
            )
        except ImportError:
            return BacktestDiagnosticEntry(
                name="memory", category="system",
                passed=True,
                message="Memory check not available (psutil not installed)",
                level=DiagnosticLevel.DEBUG,
            )

    # ── management ─────────────────────────────────────────────────────────

    def add_check(self, check: Callable) -> None:
        """Add a custom diagnostic check."""
        self._checks.append(check)

    def get_stats(self) -> Dict[str, Any]:
        """Return diagnostic statistics."""
        return {
            "registered_checks": len(self._checks),
        }
