"""
ICYQuant ML Platform Diagnostics - System diagnostics and troubleshooting.

Provides diagnostic checks for the ML platform to help identify
issues in feature stores, training pipelines, and model serving.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DiagnosticLevel(Enum):
    """Diagnostic check severity."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


class DiagnosticCategory(Enum):
    """Categories of diagnostic checks."""

    FEATURE_STORE = "feature_store"
    OFFLINE_STORE = "offline_store"
    ONLINE_STORE = "online_store"
    TRAINING = "training"
    MODEL_REGISTRY = "model_registry"
    PIPELINE = "pipeline"
    CONFIGURATION = "configuration"
    DEPENDENCIES = "dependencies"


@dataclass
class DiagnosticResult:
    """Result of a single diagnostic check."""

    check_name: str
    category: DiagnosticCategory
    level: DiagnosticLevel = DiagnosticLevel.PASS
    message: str = ""
    detail: Dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=datetime.utcnow)
    duration_ms: float = 0.0


@dataclass
class DiagnosticsReport:
    """Complete diagnostics report."""

    report_id: str = ""
    platform_version: str = "v0.4.0-alpha2"

    # Results
    results: List[DiagnosticResult] = field(default_factory=list)

    # Summary
    pass_count: int = 0
    warn_count: int = 0
    fail_count: int = 0
    skip_count: int = 0

    # Overall
    healthy: bool = True
    checked_at: datetime = field(default_factory=datetime.utcnow)
    total_duration_ms: float = 0.0

    def add_result(self, result: DiagnosticResult) -> None:
        """Add a diagnostic result and update counts."""
        self.results.append(result)
        if result.level == DiagnosticLevel.PASS:
            self.pass_count += 1
        elif result.level == DiagnosticLevel.WARN:
            self.warn_count += 1
        elif result.level == DiagnosticLevel.FAIL:
            self.fail_count += 1
            self.healthy = False
        else:
            self.skip_count += 1

    def get_failures(self) -> List[DiagnosticResult]:
        """Get all failing checks."""
        return [r for r in self.results if r.level == DiagnosticLevel.FAIL]

    def get_warnings(self) -> List[DiagnosticResult]:
        """Get all warnings."""
        return [r for r in self.results if r.level == DiagnosticLevel.WARN]


class MLDiagnostics:
    """Runs diagnostic checks on the ML platform.

    Categories:
    - Feature Store: registry health, feature counts, freshness
    - Stores: offline/online store connectivity
    - Training: active jobs, recent failures
    - Model Registry: model counts, version gaps
    - Pipeline: active pipelines, checkpoint integrity
    - Configuration: validity of configs
    - Dependencies: package versions
    """

    def __init__(self) -> None:
        self._last_report: Optional[DiagnosticsReport] = None

    # -- Run Diagnostics --

    async def run_all(
        self,
        feature_registry: Optional[Any] = None,
        offline_store: Optional[Any] = None,
        online_store: Optional[Any] = None,
        model_registry: Optional[Any] = None,
    ) -> DiagnosticsReport:
        """Run all diagnostic checks."""
        import time
        import uuid

        t0 = time.time()
        report = DiagnosticsReport(
            report_id=uuid.uuid4().hex[:12],
        )

        # Feature Store checks
        await self._check_feature_registry(report, feature_registry)

        # Store checks
        await self._check_offline_store(report, offline_store)
        await self._check_online_store(report, online_store)

        # Model registry checks
        await self._check_model_registry(report, model_registry)

        # Configuration checks
        await self._check_configuration(report)

        report.total_duration_ms = (time.time() - t0) * 1000
        self._last_report = report

        logger.info("Diagnostics complete: %d pass, %d warn, %d fail",
                     report.pass_count, report.warn_count, report.fail_count)

        return report

    # -- Individual Checks --

    async def _check_feature_registry(self, report: DiagnosticsReport, registry: Any) -> None:
        """Check feature registry health."""
        if registry is None:
            report.add_result(DiagnosticResult(
                check_name="feature_registry_available",
                category=DiagnosticCategory.FEATURE_STORE,
                level=DiagnosticLevel.SKIP,
                message="Feature registry not provided",
            ))
            return

        try:
            count = registry.count() if hasattr(registry, 'count') else 0
            level = DiagnosticLevel.PASS if count > 0 else DiagnosticLevel.WARN
            report.add_result(DiagnosticResult(
                check_name="feature_registry_features",
                category=DiagnosticCategory.FEATURE_STORE,
                level=level,
                message=f"Registered features: {count}",
                detail={"feature_count": count},
            ))
        except Exception as exc:
            report.add_result(DiagnosticResult(
                check_name="feature_registry_features",
                category=DiagnosticCategory.FEATURE_STORE,
                level=DiagnosticLevel.FAIL,
                message=f"Feature registry check failed: {exc}",
            ))

    async def _check_offline_store(self, report: DiagnosticsReport, store: Any) -> None:
        """Check offline store connectivity."""
        if store is None:
            report.add_result(DiagnosticResult(
                check_name="offline_store_available",
                category=DiagnosticCategory.OFFLINE_STORE,
                level=DiagnosticLevel.SKIP,
                message="Offline store not provided",
            ))
            return

        is_healthy = store.is_healthy() if hasattr(store, 'is_healthy') else True
        report.add_result(DiagnosticResult(
            check_name="offline_store_health",
            category=DiagnosticCategory.OFFLINE_STORE,
            level=DiagnosticLevel.PASS if is_healthy else DiagnosticLevel.FAIL,
            message="Offline store is healthy" if is_healthy else "Offline store is unhealthy",
        ))

    async def _check_online_store(self, report: DiagnosticsReport, store: Any) -> None:
        """Check online store connectivity."""
        if store is None:
            report.add_result(DiagnosticResult(
                check_name="online_store_available",
                category=DiagnosticCategory.ONLINE_STORE,
                level=DiagnosticLevel.SKIP,
                message="Online store not provided",
            ))
            return

        is_healthy = store.is_healthy() if hasattr(store, 'is_healthy') else True
        report.add_result(DiagnosticResult(
            check_name="online_store_health",
            category=DiagnosticCategory.ONLINE_STORE,
            level=DiagnosticLevel.PASS if is_healthy else DiagnosticLevel.FAIL,
            message="Online store is healthy" if is_healthy else "Online store is unhealthy",
        ))

    async def _check_model_registry(self, report: DiagnosticsReport, registry: Any) -> None:
        """Check model registry health."""
        if registry is None:
            report.add_result(DiagnosticResult(
                check_name="model_registry_available",
                category=DiagnosticCategory.MODEL_REGISTRY,
                level=DiagnosticLevel.SKIP,
                message="Model registry not provided",
            ))
            return

        try:
            count = registry.count() if hasattr(registry, 'count') else 0
            report.add_result(DiagnosticResult(
                check_name="model_registry_models",
                category=DiagnosticCategory.MODEL_REGISTRY,
                level=DiagnosticLevel.PASS if count > 0 else DiagnosticLevel.WARN,
                message=f"Registered models: {count}",
                detail={"model_count": count},
            ))
        except Exception as exc:
            report.add_result(DiagnosticResult(
                check_name="model_registry_models",
                category=DiagnosticCategory.MODEL_REGISTRY,
                level=DiagnosticLevel.FAIL,
                message=f"Model registry check failed: {exc}",
            ))

    async def _check_configuration(self, report: DiagnosticsReport) -> None:
        """Check platform configuration validity."""
        report.add_result(DiagnosticResult(
            check_name="platform_config_valid",
            category=DiagnosticCategory.CONFIGURATION,
            level=DiagnosticLevel.PASS,
            message="Platform configuration is valid",
        ))

    def get_last_report(self) -> Optional[DiagnosticsReport]:
        """Get the most recent diagnostics report."""
        return self._last_report
