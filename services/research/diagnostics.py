"""Research Diagnostics — diagnostics and trouble-shooting for the research platform.

Provides system diagnostics, component health verification, dependency
checking, and automated troubleshooting for research platform operations.
"""

from __future__ import annotations

import asyncio
import logging
import platform
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class DiagnosticLevel(str, Enum):
    """Severity/type of diagnostic message."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class DiagnosticStatus(str, Enum):
    """Overall diagnostic report status."""

    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass
class DiagnosticEntry:
    """A single diagnostic check result."""

    name: str
    category: str
    level: DiagnosticLevel = DiagnosticLevel.INFO
    passed: bool = True
    message: str = ""
    detail: Optional[str] = None
    suggestion: Optional[str] = None
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "level": self.level.value,
            "passed": self.passed,
            "message": self.message,
            "detail": self.detail,
            "suggestion": self.suggestion,
            "latency_ms": self.latency_ms,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class DiagnosticReport:
    """Aggregated diagnostic report across all checks."""

    status: DiagnosticStatus = DiagnosticStatus.UNKNOWN
    entries: List[DiagnosticEntry] = field(default_factory=list)
    total_checks: int = 0
    passed: int = 0
    warnings: int = 0
    errors: int = 0
    total_latency_ms: float = 0.0
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    system_info: Dict[str, Any] = field(default_factory=dict)

    def add(self, entry: DiagnosticEntry) -> None:
        self.entries.append(entry)
        self.total_checks += 1
        if not entry.passed:
            if entry.level == DiagnosticLevel.ERROR or entry.level == DiagnosticLevel.CRITICAL:
                self.errors += 1
            else:
                self.warnings += 1
        else:
            self.passed += 1
        self.total_latency_ms += entry.latency_ms

    def finalize(self) -> None:
        if self.errors > 0:
            self.status = DiagnosticStatus.FAILED
        elif self.warnings > 0:
            self.status = DiagnosticStatus.WARNING
        else:
            self.status = DiagnosticStatus.PASSED

    def failed_entries(self) -> List[DiagnosticEntry]:
        return [e for e in self.entries if not e.passed]

    def entries_by_category(self, category: str) -> List[DiagnosticEntry]:
        return [e for e in self.entries if e.category == category]

    def summary(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "total_checks": self.total_checks,
            "passed": self.passed,
            "warnings": self.warnings,
            "errors": self.errors,
            "total_latency_ms": self.total_latency_ms,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "entries": [e.to_dict() for e in self.entries],
            "total_checks": self.total_checks,
            "passed": self.passed,
            "warnings": self.warnings,
            "errors": self.errors,
            "total_latency_ms": self.total_latency_ms,
            "generated_at": self.generated_at.isoformat(),
            "system_info": self.system_info,
        }

    def __repr__(self) -> str:
        return (
            f"DiagnosticReport(status={self.status.value}, "
            f"passed={self.passed}/{self.total_checks})"
        )


class ResearchDiagnostics:
    """System diagnostics runner for the research platform.

    Performs health verification of all research platform components
    including engine, experiments, datasets, runtime, and dependencies.

    Usage::

        diag = ResearchDiagnostics()
        diag.register_checks()
        report = await diag.run()
        if report.status != DiagnosticStatus.PASSED:
            for entry in report.failed_entries():
                print(f"FAIL: {entry.name} - {entry.message}")
    """

    # Global counters
    _reports_generated: int = 0
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self) -> None:
        self._checks: Dict[str, Callable[..., DiagnosticEntry]] = {}
        self._categories: Dict[str, List[str]] = {}

    # ---- Check Registration ----

    def register(
        self,
        name: str,
        check_fn: Callable[..., DiagnosticEntry],
        category: str = "general",
    ) -> None:
        """Register a diagnostic check.

        Args:
            name: Unique check name.
            check_fn: Sync/async callable returning DiagnosticEntry.
            category: Grouping category (e.g., 'engine', 'storage', 'network').
        """
        self._checks[name] = check_fn
        self._categories.setdefault(category, []).append(name)

    def register_checks(self) -> None:
        """Register all default diagnostic checks."""
        self.register("python_version", self._check_python_version, "system")
        self.register("platform_info", self._check_platform_info, "system")
        self.register("asyncio_loop", self._check_asyncio_loop, "system")

    def unregister(self, name: str) -> bool:
        result = self._checks.pop(name, None) is not None
        for cat in self._categories.values():
            if name in cat:
                cat.remove(name)
        return result

    # ---- Execution ----

    async def run_check(self, name: str) -> DiagnosticEntry:
        """Run a single diagnostic check."""
        check_fn = self._checks.get(name)
        if check_fn is None:
            return DiagnosticEntry(
                name=name,
                category="unknown",
                level=DiagnosticLevel.ERROR,
                passed=False,
                message=f"Check '{name}' not registered",
            )
        start = time.monotonic()
        try:
            result = check_fn()
            if asyncio.iscoroutine(result):
                result = await result
            result.latency_ms = (time.monotonic() - start) * 1000
            return result
        except Exception as exc:
            return DiagnosticEntry(
                name=name,
                category="unknown",
                level=DiagnosticLevel.ERROR,
                passed=False,
                message=f"Check raised exception: {exc}",
                detail=str(exc),
                latency_ms=(time.monotonic() - start) * 1000,
            )

    async def run(self, categories: Optional[List[str]] = None) -> DiagnosticReport:
        """Run all diagnostic checks and return a report.

        Args:
            categories: Optional list of categories to filter checks.
        """
        report = DiagnosticReport(system_info=self._collect_system_info())

        check_names = list(self._checks.keys())
        if categories:
            filtered: set = set()
            for cat in categories:
                filtered.update(self._categories.get(cat, []))
            check_names = [n for n in check_names if n in filtered]

        for name in check_names:
            entry = await self.run_check(name)
            report.add(entry)

        report.finalize()
        ResearchDiagnostics._reports_generated += 1
        return report

    # ---- Built-in Checks ----

    def _check_python_version(self) -> DiagnosticEntry:
        version_info = sys.version_info
        min_version = (3, 10)
        ok = version_info >= min_version
        return DiagnosticEntry(
            name="python_version",
            category="system",
            level=DiagnosticLevel.INFO if ok else DiagnosticLevel.ERROR,
            passed=ok,
            message=f"Python {version_info.major}.{version_info.minor}.{version_info.micro}",
            suggestion=f"Upgrade to Python {min_version[0]}.{min_version[1]}+" if not ok else None,
            metadata={"version": sys.version, "min_required": f"{min_version[0]}.{min_version[1]}"},
        )

    def _check_platform_info(self) -> DiagnosticEntry:
        return DiagnosticEntry(
            name="platform_info",
            category="system",
            level=DiagnosticLevel.INFO,
            passed=True,
            message=f"{platform.system()} {platform.release()} ({platform.machine()})",
            metadata={
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "processor": platform.processor(),
            },
        )

    def _check_asyncio_loop(self) -> DiagnosticEntry:
        try:
            loop = asyncio.get_event_loop()
            return DiagnosticEntry(
                name="asyncio_loop",
                category="system",
                level=DiagnosticLevel.INFO,
                passed=True,
                message=f"Event loop running: {loop.is_running()}",
                metadata={"is_running": loop.is_running()},
            )
        except Exception as exc:
            return DiagnosticEntry(
                name="asyncio_loop",
                category="system",
                level=DiagnosticLevel.ERROR,
                passed=False,
                message=f"Cannot get event loop: {exc}",
            )

    # ---- Helpers ----

    @staticmethod
    def _collect_system_info() -> Dict[str, Any]:
        return {
            "python_version": sys.version,
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def list_checks(self) -> List[Dict[str, Any]]:
        return [
            {"name": name, "category": self._get_category(name)}
            for name in self._checks
        ]

    def _get_category(self, name: str) -> str:
        for cat, names in self._categories.items():
            if name in names:
                return cat
        return "unknown"

    @property
    def reports_generated(self) -> int:
        return ResearchDiagnostics._reports_generated

    def __repr__(self) -> str:
        return (
            f"ResearchDiagnostics(checks={len(self._checks)}, "
            f"categories={len(self._categories)})"
        )
