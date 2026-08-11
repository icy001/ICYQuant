"""Platform Diagnostics — performance diagnostics and health analysis for the AI Platform.

Analyzes platform-wide performance, detects issues, and generates
diagnostic reports for troubleshooting and optimization.

Diagnostics dimensions:
    - Request latency breakdown by component
    - Model call success rate and latency
    - Provider availability trends
    - Budget utilization and cost trends
    - Guardrail and policy violation rates
    - Agent health and throughput
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DiagnosticIssue:
    """A detected diagnostic issue."""
    component: str = ""
    severity: str = "info"  # info, warning, error
    message: str = ""
    recommendation: str = ""
    detected_at: float = field(default_factory=time.monotonic)


@dataclass
class DiagnosticReport:
    """Complete diagnostic report for the AI Platform."""
    generated_at: float = field(default_factory=time.monotonic)
    overall_status: str = "healthy"  # healthy, degraded, critical
    request_latency_p50_ms: float = 0.0
    request_latency_p95_ms: float = 0.0
    request_latency_p99_ms: float = 0.0
    model_success_rate: float = 1.0
    provider_availability: Dict[str, bool] = field(default_factory=dict)
    guardrail_block_rate: float = 0.0
    cost_per_request_avg: float = 0.0
    issues: List[DiagnosticIssue] = field(default_factory=list)
    agent_health_summary: Dict[str, str] = field(default_factory=dict)


class PlatformDiagnostics:
    """Performance diagnostics for the AI Platform.

    Analyzes platform performance, detects issues, and generates
    diagnostic reports for troubleshooting.

    Usage:
        diag = PlatformDiagnostics()
        await diag.initialize()
        report = await diag.run_diagnostics(metrics_data)
    """

    def __init__(self) -> None:
        self._reports: List[DiagnosticReport] = []
        self._max_reports: int = 200
        self._initialized: bool = False
        self._lock = threading.Lock()
        logger.info("PlatformDiagnostics created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("PlatformDiagnostics initialized")

    async def shutdown(self) -> None:
        with self._lock:
            self._reports.clear()
        self._initialized = False
        logger.info("PlatformDiagnostics shutdown complete")

    async def run_diagnostics(self, metrics_data: Optional[Dict[str, Any]] = None) -> DiagnosticReport:
        """Run a full diagnostic scan of the AI Platform.

        Args:
            metrics_data: Optional current metrics snapshot for analysis.
        """
        report = DiagnosticReport()
        issues: List[DiagnosticIssue] = []

        # Analyze from metrics data if provided
        if metrics_data:
            # Check error rate
            total = metrics_data.get("total_requests", 0)
            errors = metrics_data.get("total_errors", 0)
            if total > 0:
                error_rate = errors / total
                if error_rate > 0.10:
                    issues.append(DiagnosticIssue(
                        component="platform",
                        severity="error",
                        message=f"High error rate: {error_rate*100:.1f}%",
                        recommendation="Investigate failing components and check provider availability",
                    ))
                    report.overall_status = "critical"
                elif error_rate > 0.05:
                    issues.append(DiagnosticIssue(
                        component="platform",
                        severity="warning",
                        message=f"Elevated error rate: {error_rate*100:.1f}%",
                        recommendation="Monitor error trends and check provider health",
                    ))
                    report.overall_status = "degraded"

            # Check latency
            p95 = metrics_data.get("latency_p95_ms", 0)
            if p95 > 5000:
                issues.append(DiagnosticIssue(
                    component="model_router",
                    severity="warning",
                    message=f"High p95 latency: {p95:.0f}ms",
                    recommendation="Consider switching to faster models or providers",
                ))
                if report.overall_status == "healthy":
                    report.overall_status = "degraded"

            # Check model success rate
            model_success = metrics_data.get("model_success_rate", 1.0)
            report.model_success_rate = model_success
            if model_success < 0.90:
                issues.append(DiagnosticIssue(
                    component="model_router",
                    severity="error",
                    message=f"Low model success rate: {model_success*100:.1f}%",
                    recommendation="Check provider health and fallback configuration",
                ))
                report.overall_status = "critical"

            # Check guardrail blocks
            guardrail_blocks = metrics_data.get("guardrail_blocks", 0)
            total_req = max(total, 1)
            report.guardrail_block_rate = guardrail_blocks / total_req
            if report.guardrail_block_rate > 0.20:
                issues.append(DiagnosticIssue(
                    component="guardrail_engine",
                    severity="warning",
                    message=f"High guardrail block rate: {report.guardrail_block_rate*100:.1f}%",
                    recommendation="Review guardrail rules for false positives",
                ))

            report.request_latency_p50_ms = metrics_data.get("latency_p50_ms", 0)
            report.request_latency_p95_ms = metrics_data.get("latency_p95_ms", 0)
            report.request_latency_p99_ms = metrics_data.get("latency_p99_ms", 0)

        report.issues = issues

        with self._lock:
            self._reports.append(report)
            if len(self._reports) > self._max_reports:
                self._reports = self._reports[-self._max_reports:]

        logger.info("PlatformDiagnostics: report generated (status=%s, issues=%d)", report.overall_status, len(issues))
        return report

    def get_latest_report(self) -> Optional[DiagnosticReport]:
        with self._lock:
            return self._reports[-1] if self._reports else None

    def get_reports(self, limit: int = 20) -> List[DiagnosticReport]:
        with self._lock:
            return list(reversed(self._reports[-limit:]))

    def get_summary(self) -> Dict[str, Any]:
        latest = self.get_latest_report()
        return {
            "initialized": self._initialized,
            "total_reports": len(self._reports),
            "latest_status": latest.overall_status if latest else "unknown",
            "latest_issues": len(latest.issues) if latest else 0,
        }
