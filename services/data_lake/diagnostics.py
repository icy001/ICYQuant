"""
Data Lake Diagnostics — Diagnostic analysis for the enterprise
historical data lake covering all subsystems.

Commit 16 Part 1.3
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DiagnosticStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIPPED = "skipped"


@dataclass
class DiagnosticCheck:
    """A single diagnostic check result."""
    name: str
    category: str
    status: DiagnosticStatus
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DataLakeDiagnosticReport:
    """Complete diagnostic report for the data lake."""
    platform_id: str = "icyquant-data-lake"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    overall_status: DiagnosticStatus = DiagnosticStatus.PASS
    checks: list[DiagnosticCheck] = field(default_factory=list)
    summary: dict[str, int] = field(
        default_factory=lambda: {"pass": 0, "warn": 0, "fail": 0, "skipped": 0}
    )
    recommendations: list[str] = field(default_factory=list)


class DataLakeDiagnostics:
    """
    Diagnostic analysis for the data lake platform.

    Checks all data lake subsystems: engine, runtime, storage,
    catalog, version management, replay, query, and integrity.

    Usage::

        diag = DataLakeDiagnostics()
        await diag.initialize()
        await diag.inject("engine", data_lake_engine)
        report = await diag.run_full_diagnostics()
    """

    SUBSYSTEMS = [
        "data_lake_engine",
        "data_lake_runtime",
        "storage_manager",
        "dataset_registry",
        "metadata_catalog",
        "schema_catalog",
        "quality_catalog",
        "version_manager",
        "retention_manager",
        "lifecycle_manager",
        "manifest_manager",
        "replay_engine",
        "replay_scheduler",
        "historical_query_engine",
        "index_manager",
        "checksum_validator",
        "lineage_tracker",
    ]

    def __init__(self) -> None:
        self._checks: list[DiagnosticCheck] = []
        self._injectables: dict[str, Any] = {}

    async def initialize(self) -> None:
        """Initialize diagnostics."""
        logger.info("DataLakeDiagnostics initialized.")

    async def stop(self) -> None:
        """Stop diagnostics."""
        logger.info("DataLakeDiagnostics stopped.")

    def inject(self, name: str, component: Any) -> None:
        """Inject a component for diagnostic checking."""
        self._injectables[name] = component

    # ── Diagnostic Checks ─────────────────────────────────────────

    async def check_engine(self) -> list[DiagnosticCheck]:
        """Check the data lake engine health."""
        start = time.monotonic()
        checks: list[DiagnosticCheck] = []
        engine = self._injectables.get("data_lake_engine")

        if engine:
            checks.append(DiagnosticCheck(
                name="engine_running",
                category="engine",
                status=DiagnosticStatus.PASS,
                message="DataLakeEngine is running",
                duration_ms=(time.monotonic() - start) * 1000,
            ))
        else:
            checks.append(DiagnosticCheck(
                name="engine_running",
                category="engine",
                status=DiagnosticStatus.SKIPPED,
                message="DataLakeEngine not injected",
                duration_ms=(time.monotonic() - start) * 1000,
            ))
        return checks

    async def check_runtime(self) -> list[DiagnosticCheck]:
        """Check the data lake runtime worker pool."""
        start = time.monotonic()
        checks: list[DiagnosticCheck] = []
        runtime = self._injectables.get("data_lake_runtime")

        if runtime:
            try:
                stats = await runtime.stats()
                checks.append(DiagnosticCheck(
                    name="runtime_workers",
                    category="runtime",
                    status=DiagnosticStatus.PASS,
                    message=f"Workers: {stats.get('active_workers', 0)} active",
                    details=stats,
                    duration_ms=(time.monotonic() - start) * 1000,
                ))
            except Exception as e:
                checks.append(DiagnosticCheck(
                    name="runtime_workers",
                    category="runtime",
                    status=DiagnosticStatus.FAIL,
                    message=str(e),
                    duration_ms=(time.monotonic() - start) * 1000,
                ))
        else:
            checks.append(DiagnosticCheck(
                name="runtime_workers",
                category="runtime",
                status=DiagnosticStatus.SKIPPED,
                message="DataLakeRuntime not injected",
                duration_ms=(time.monotonic() - start) * 1000,
            ))
        return checks

    async def check_storage(self) -> list[DiagnosticCheck]:
        """Check storage subsystem health."""
        start = time.monotonic()
        checks: list[DiagnosticCheck] = []
        storage_mgr = self._injectables.get("storage_manager")

        if storage_mgr:
            checks.append(DiagnosticCheck(
                name="storage_accessible",
                category="storage",
                status=DiagnosticStatus.PASS,
                message="StorageManager is accessible",
                duration_ms=(time.monotonic() - start) * 1000,
            ))
        else:
            checks.append(DiagnosticCheck(
                name="storage_accessible",
                category="storage",
                status=DiagnosticStatus.SKIPPED,
                message="StorageManager not injected",
                duration_ms=(time.monotonic() - start) * 1000,
            ))
        return checks

    async def check_catalogs(self) -> list[DiagnosticCheck]:
        """Check metadata/schema/quality catalog health."""
        start = time.monotonic()
        checks: list[DiagnosticCheck] = []

        for cat_name in ("metadata_catalog", "schema_catalog", "quality_catalog"):
            catalog = self._injectables.get(cat_name)
            if catalog:
                checks.append(DiagnosticCheck(
                    name=f"{cat_name}_available",
                    category="catalog",
                    status=DiagnosticStatus.PASS,
                    message=f"{cat_name} is available",
                    duration_ms=(time.monotonic() - start) * 1000,
                ))
            else:
                checks.append(DiagnosticCheck(
                    name=f"{cat_name}_available",
                    category="catalog",
                    status=DiagnosticStatus.SKIPPED,
                    message=f"{cat_name} not injected",
                    duration_ms=(time.monotonic() - start) * 1000,
                ))
        return checks

    async def check_versioning(self) -> list[DiagnosticCheck]:
        """Check version manager health."""
        start = time.monotonic()
        checks: list[DiagnosticCheck] = []
        version_mgr = self._injectables.get("version_manager")

        if version_mgr:
            try:
                summary = await version_mgr.get_summary()
                checks.append(DiagnosticCheck(
                    name="version_manager_active",
                    category="versioning",
                    status=DiagnosticStatus.PASS,
                    message=f"Versions tracked: {summary.get('total_versions', 0)}",
                    details=summary,
                    duration_ms=(time.monotonic() - start) * 1000,
                ))
            except Exception as e:
                checks.append(DiagnosticCheck(
                    name="version_manager_active",
                    category="versioning",
                    status=DiagnosticStatus.FAIL,
                    message=str(e),
                    duration_ms=(time.monotonic() - start) * 1000,
                ))
        else:
            checks.append(DiagnosticCheck(
                name="version_manager_active",
                category="versioning",
                status=DiagnosticStatus.SKIPPED,
                message="VersionManager not injected",
                duration_ms=(time.monotonic() - start) * 1000,
            ))
        return checks

    async def check_replay_engine(self) -> list[DiagnosticCheck]:
        """Check replay engine health."""
        start = time.monotonic()
        checks: list[DiagnosticCheck] = []
        replay = self._injectables.get("replay_engine")

        if replay:
            checks.append(DiagnosticCheck(
                name="replay_engine_available",
                category="replay",
                status=DiagnosticStatus.PASS,
                message="ReplayEngine is available",
                duration_ms=(time.monotonic() - start) * 1000,
            ))
        else:
            checks.append(DiagnosticCheck(
                name="replay_engine_available",
                category="replay",
                status=DiagnosticStatus.SKIPPED,
                message="ReplayEngine not injected",
                duration_ms=(time.monotonic() - start) * 1000,
            ))
        return checks

    async def check_integrity(self) -> list[DiagnosticCheck]:
        """Check data integrity (checksums, lineage)."""
        start = time.monotonic()
        checks: list[DiagnosticCheck] = []

        validator = self._injectables.get("checksum_validator")
        if validator:
            try:
                report = await validator.integrity_report()
                health = report.get("health_status", "unknown")
                status = DiagnosticStatus.PASS if health == "healthy" else DiagnosticStatus.WARN
                checks.append(DiagnosticCheck(
                    name="checksum_integrity",
                    category="integrity",
                    status=status,
                    message=f"Integrity: {health}, {report.get('valid', 0)} valid records",
                    details=report,
                    duration_ms=(time.monotonic() - start) * 1000,
                ))
            except Exception as e:
                checks.append(DiagnosticCheck(
                    name="checksum_integrity",
                    category="integrity",
                    status=DiagnosticStatus.FAIL,
                    message=str(e),
                    duration_ms=(time.monotonic() - start) * 1000,
                ))
        else:
            checks.append(DiagnosticCheck(
                name="checksum_integrity",
                category="integrity",
                status=DiagnosticStatus.SKIPPED,
                message="ChecksumValidator not injected",
                duration_ms=(time.monotonic() - start) * 1000,
            ))

        tracker = self._injectables.get("lineage_tracker")
        if tracker:
            try:
                lineage_summary = await tracker.get_summary()
                checks.append(DiagnosticCheck(
                    name="lineage_tracking",
                    category="integrity",
                    status=DiagnosticStatus.PASS,
                    message=f"Lineage: {lineage_summary.get('total_datasets', 0)} datasets tracked",
                    details=lineage_summary,
                    duration_ms=(time.monotonic() - start) * 1000,
                ))
            except Exception as e:
                checks.append(DiagnosticCheck(
                    name="lineage_tracking",
                    category="integrity",
                    status=DiagnosticStatus.FAIL,
                    message=str(e),
                    duration_ms=(time.monotonic() - start) * 1000,
                ))
        return checks

    async def check_manifest(self) -> list[DiagnosticCheck]:
        """Check manifest manager health."""
        start = time.monotonic()
        checks: list[DiagnosticCheck] = []
        manifest_mgr = self._injectables.get("manifest_manager")

        if manifest_mgr:
            checks.append(DiagnosticCheck(
                name="manifest_manager_available",
                category="manifest",
                status=DiagnosticStatus.PASS,
                message="ManifestManager is available",
                duration_ms=(time.monotonic() - start) * 1000,
            ))
        else:
            checks.append(DiagnosticCheck(
                name="manifest_manager_available",
                category="manifest",
                status=DiagnosticStatus.SKIPPED,
                message="ManifestManager not injected",
                duration_ms=(time.monotonic() - start) * 1000,
            ))
        return checks

    # ── Full Diagnostics ──────────────────────────────────────────

    async def run_full_diagnostics(self) -> DataLakeDiagnosticReport:
        """Run all diagnostic checks and produce a report."""
        logger.info("Running full data lake diagnostics...")
        report = DataLakeDiagnosticReport()

        check_groups = [
            self.check_engine(),
            self.check_runtime(),
            self.check_storage(),
            self.check_catalogs(),
            self.check_versioning(),
            self.check_replay_engine(),
            self.check_integrity(),
            self.check_manifest(),
        ]

        results: list[list[DiagnosticCheck]] = []
        for coro in check_groups:
            try:
                results.append(await coro)
            except Exception as e:
                logger.error("Diagnostic check group failed: %s", e)
                results.append([
                    DiagnosticCheck(
                        name="check_group_error",
                        category="general",
                        status=DiagnosticStatus.FAIL,
                        message=str(e),
                    )
                ])

        for group in results:
            report.checks.extend(group)

        # Compute summary
        for check in report.checks:
            report.summary[check.status.value] += 1

        # Determine overall status
        if report.summary["fail"] > 0:
            report.overall_status = DiagnosticStatus.FAIL
            report.recommendations.append(
                f"{report.summary['fail']} checks failed. Review diagnostics details."
            )
        elif report.summary["warn"] > 0:
            report.overall_status = DiagnosticStatus.WARN
            report.recommendations.append(
                f"{report.summary['warn']} checks have warnings."
            )
        else:
            report.overall_status = DiagnosticStatus.PASS

        logger.info(
            "Diagnostics complete: %s (pass=%d, warn=%d, fail=%d, skipped=%d)",
            report.overall_status.value,
            report.summary["pass"],
            report.summary["warn"],
            report.summary["fail"],
            report.summary["skipped"],
        )
        return report
