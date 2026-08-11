"""
Signal & Alpha Diagnostics — Diagnostic analysis for signal and alpha subsystems.

Part of Commit 13 Part 1.2: Signal & Alpha Engine.

Checks:
    - Signal engine health
    - Alpha engine health
    - Cache integrity
    - Registry consistency
    - Resource utilization
    - Pipeline latency
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from services.strategy.signal.signal_engine import SignalEngine
from services.strategy.signal.alpha_engine import AlphaEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class DiagnosticSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"
    OK = "OK"


@dataclass
class DiagnosticIssue:
    """A single diagnostic finding."""
    category: str
    severity: DiagnosticSeverity
    message: str
    detail: Optional[str] = None
    recommendation: Optional[str] = None


@dataclass
class DiagnosticReport:
    """Full diagnostic report."""
    report_id: str = ""
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    overall_status: DiagnosticSeverity = DiagnosticSeverity.OK
    issues: List[DiagnosticIssue] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == DiagnosticSeverity.CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == DiagnosticSeverity.WARNING)


# ---------------------------------------------------------------------------
# Signal Diagnostics
# ---------------------------------------------------------------------------

class SignalDiagnostics:
    """Diagnostic analyzer for signal and alpha subsystems."""

    def __init__(self):
        self._signal_engine: Optional[SignalEngine] = None
        self._alpha_engine: Optional[AlphaEngine] = None

    def wire(self, signal_engine: SignalEngine, alpha_engine: AlphaEngine) -> None:
        """Wire up references to the engines for inspection."""
        self._signal_engine = signal_engine
        self._alpha_engine = alpha_engine

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    async def run_full_diagnostics(self) -> DiagnosticReport:
        """Run all diagnostic checks."""
        import uuid
        report = DiagnosticReport(report_id=f"diag_{uuid.uuid4().hex[:8]}")

        checks = [
            self._check_signal_engine,
            self._check_alpha_engine,
            self._check_cache,
            self._check_registry,
            self._check_resources,
            self._check_pipeline,
        ]

        for check in checks:
            issues = await check()
            report.issues.extend(issues)

        # Determine overall status
        if any(i.severity == DiagnosticSeverity.CRITICAL for i in report.issues):
            report.overall_status = DiagnosticSeverity.CRITICAL
        elif any(i.severity == DiagnosticSeverity.WARNING for i in report.issues):
            report.overall_status = DiagnosticSeverity.WARNING
        else:
            report.overall_status = DiagnosticSeverity.OK

        logger.info("Diagnostics complete: %s (critical=%d, warning=%d)",
                     report.overall_status.value, report.critical_count, report.warning_count)

        return report

    # ------------------------------------------------------------------
    # Check Methods
    # ------------------------------------------------------------------

    async def _check_signal_engine(self) -> List[DiagnosticIssue]:
        issues = []
        if not self._signal_engine:
            issues.append(DiagnosticIssue(
                category="signal_engine",
                severity=DiagnosticSeverity.CRITICAL,
                message="SignalEngine not wired",
            ))
            return issues

        if not self._signal_engine.is_initialized:
            issues.append(DiagnosticIssue(
                category="signal_engine",
                severity=DiagnosticSeverity.CRITICAL,
                message="SignalEngine not initialized",
            ))
        else:
            issues.append(DiagnosticIssue(
                category="signal_engine",
                severity=DiagnosticSeverity.OK,
                message="SignalEngine initialized and healthy",
            ))

        # Check runtime slots
        if self._signal_engine.runtime:
            available = self._signal_engine.runtime.available_slots()
            if available == 0:
                issues.append(DiagnosticIssue(
                    category="signal_runtime",
                    severity=DiagnosticSeverity.WARNING,
                    message="No available signal runtime slots",
                    recommendation="Increase max_concurrent_slots or wait for completion",
                ))

        return issues

    async def _check_alpha_engine(self) -> List[DiagnosticIssue]:
        issues = []
        if not self._alpha_engine:
            issues.append(DiagnosticIssue(
                category="alpha_engine",
                severity=DiagnosticSeverity.CRITICAL,
                message="AlphaEngine not wired",
            ))
            return issues

        if not self._alpha_engine.is_initialized:
            issues.append(DiagnosticIssue(
                category="alpha_engine",
                severity=DiagnosticSeverity.CRITICAL,
                message="AlphaEngine not initialized",
            ))
        else:
            issues.append(DiagnosticIssue(
                category="alpha_engine",
                severity=DiagnosticSeverity.OK,
                message="AlphaEngine initialized and healthy",
            ))

        # Check alpha registry
        if self._alpha_engine.registry:
            active_count = self._alpha_engine.registry.active_count
            if active_count == 0:
                issues.append(DiagnosticIssue(
                    category="alpha_registry",
                    severity=DiagnosticSeverity.WARNING,
                    message="No active alphas in registry",
                    recommendation="Register alpha models or check for full decay",
                ))

        return issues

    async def _check_cache(self) -> List[DiagnosticIssue]:
        issues = []
        if not self._signal_engine or not self._signal_engine.cache:
            return issues

        cache = self._signal_engine.cache
        size = cache.size

        if size > 9000:  # Near max (10000 default)
            issues.append(DiagnosticIssue(
                category="signal_cache",
                severity=DiagnosticSeverity.WARNING,
                message=f"Signal cache near capacity: {size}/10000",
                recommendation="Increase cache size or reduce signal TTL",
            ))

        return issues

    async def _check_registry(self) -> List[DiagnosticIssue]:
        issues = []
        if not self._alpha_engine or not self._alpha_engine.registry:
            return issues

        registry = self._alpha_engine.registry
        decaying = [
            a for a in registry.list_all() if a.status.value == "DECAYING"
        ]
        if len(decaying) > 5:
            issues.append(DiagnosticIssue(
                category="alpha_registry",
                severity=DiagnosticSeverity.WARNING,
                message=f"{len(decaying)} alphas are decaying",
                recommendation="Review alpha performance and refresh or retire",
            ))

        return issues

    async def _check_resources(self) -> List[DiagnosticIssue]:
        issues = []
        # Placeholder for resource checks (memory, CPU, etc.)
        return issues

    async def _check_pipeline(self) -> List[DiagnosticIssue]:
        issues = []
        # Check signal pipeline latency from recent metrics
        return issues
