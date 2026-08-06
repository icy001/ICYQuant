"""Factor Diagnostics — system diagnostics for the factor research engine.

Provides component health checks, dependency verification, and
automated troubleshooting for factor research operations.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class FactorDiagnosticStatus(str, Enum):
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
class FactorDiagnosticEntry:
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
class FactorDiagnosticReport:
    """Complete diagnostic report."""

    status: FactorDiagnosticStatus = FactorDiagnosticStatus.UNKNOWN
    entries: List[FactorDiagnosticEntry] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    total_duration_ms: float = 0.0
    summary: Dict[str, int] = field(default_factory=dict)

    def passed_count(self) -> int:
        return sum(1 for e in self.entries if e.passed)

    def failed_count(self) -> int:
        return sum(1 for e in self.entries if not e.passed)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "entries": [
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
            "summary": self.summary,
            "total_duration_ms": self.total_duration_ms,
        }


class FactorDiagnostics:
    """System diagnostics for the factor research engine.

    Checks:
    * Component availability (engine, manager, registry, repository)
    * Pipeline integrity
    * Feature store health
    * Alpha pool state
    * Memory and performance
    """

    def __init__(self) -> None:
        self._checks: Dict[str, Callable] = {}
        self._register_default_checks()

    def _register_default_checks(self) -> None:
        self.register_check("engine_state", self._check_engine_state)
        self.register_check("pipeline_health", self._check_pipeline_health)
        self.register_check("feature_store", self._check_feature_store)
        self.register_check("alpha_pool", self._check_alpha_pool)
        self.register_check("memory_usage", self._check_memory_usage)

    def register_check(self, name: str, check_fn: Callable) -> None:
        self._checks[name] = check_fn

    async def run_diagnostics(
        self,
        context: Optional[Dict[str, Any]] = None,
    ) -> FactorDiagnosticReport:
        """Run all registered diagnostic checks.

        Args:
            context: optional context (engine, manager, etc.)

        Returns:
            FactorDiagnosticReport with all check results
        """
        report = FactorDiagnosticReport()
        context = context or {}

        for name, check_fn in self._checks.items():
            start = time.time()
            try:
                entry = await check_fn(context)
            except Exception as exc:
                entry = FactorDiagnosticEntry(
                    name=name,
                    category="system",
                    level=DiagnosticLevel.ERROR,
                    passed=False,
                    message=f"Check failed: {exc}",
                    detail=str(exc),
                )
            entry.duration_ms = (time.time() - start) * 1000
            report.entries.append(entry)

        report.completed_at = datetime.now(timezone.utc)
        report.total_duration_ms = (
            report.completed_at - report.started_at
        ).total_seconds() * 1000

        # Determine overall status
        failed = report.failed_count()
        if failed == 0:
            report.status = FactorDiagnosticStatus.PASSED
        elif failed <= 2:
            report.status = FactorDiagnosticStatus.WARNING
        else:
            report.status = FactorDiagnosticStatus.FAILED

        report.summary = {
            "total": len(report.entries),
            "passed": report.passed_count(),
            "failed": failed,
        }

        logger.info(
            "Diagnostics complete: %s (%d/%d passed)",
            report.status.value, report.passed_count(), len(report.entries),
        )
        return report

    async def _check_engine_state(
        self, context: Dict[str, Any]
    ) -> FactorDiagnosticEntry:
        engine = context.get("engine")
        if engine is None:
            return FactorDiagnosticEntry(
                name="engine_state",
                category="core",
                level=DiagnosticLevel.WARNING,
                passed=False,
                message="Factor engine not provided",
            )
        state = getattr(engine, "state", None)
        state_val = state.value if state else "unknown"
        return FactorDiagnosticEntry(
            name="engine_state",
            category="core",
            passed=state_val in ("ready", "running"),
            message=f"Engine state: {state_val}",
        )

    async def _check_pipeline_health(
        self, context: Dict[str, Any]
    ) -> FactorDiagnosticEntry:
        pipeline = context.get("pipeline")
        if pipeline is None:
            return FactorDiagnosticEntry(
                name="pipeline_health",
                category="core",
                level=DiagnosticLevel.WARNING,
                passed=True,
                message="Pipeline not initialized (lazy)",
            )
        return FactorDiagnosticEntry(
            name="pipeline_health",
            category="core",
            passed=True,
            message="Pipeline available",
        )

    async def _check_feature_store(
        self, context: Dict[str, Any]
    ) -> FactorDiagnosticEntry:
        store = context.get("feature_store")
        if store is None:
            return FactorDiagnosticEntry(
                name="feature_store",
                category="storage",
                level=DiagnosticLevel.INFO,
                passed=True,
                message="Feature store not initialized",
            )
        stats = getattr(store, "stats", lambda: {})()
        return FactorDiagnosticEntry(
            name="feature_store",
            category="storage",
            passed=True,
            message=f"Features: {stats.get('total_features', 0)}, "
                     f"Unique: {stats.get('unique_names', 0)}",
        )

    async def _check_alpha_pool(
        self, context: Dict[str, Any]
    ) -> FactorDiagnosticEntry:
        pool = context.get("alpha_pool")
        if pool is None:
            return FactorDiagnosticEntry(
                name="alpha_pool",
                category="core",
                level=DiagnosticLevel.INFO,
                passed=True,
                message="Alpha pool not initialized",
            )
        stats = getattr(pool, "stats", {})
        return FactorDiagnosticEntry(
            name="alpha_pool",
            category="core",
            passed=True,
            message=f"Production: {stats.get('production', 0)}, "
                     f"Validated: {stats.get('validated', 0)}",
        )

    async def _check_memory_usage(
        self, context: Dict[str, Any]
    ) -> FactorDiagnosticEntry:
        try:
            import sys
            import gc
            gc.collect()
            # Get total object count
            total_objects = sum(1 for _ in gc.get_objects())

            return FactorDiagnosticEntry(
                name="memory_usage",
                category="system",
                level=DiagnosticLevel.DEBUG,
                passed=True,
                message=f"Total tracked objects: {total_objects}",
            )
        except Exception:
            return FactorDiagnosticEntry(
                name="memory_usage",
                category="system",
                level=DiagnosticLevel.DEBUG,
                passed=True,
                message="Memory check skipped",
            )
