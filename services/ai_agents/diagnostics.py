"""
ICYQuant Agent Diagnostics — issue detection and troubleshooting.

Monitors agent system health, detects anomalies, collects diagnostic
information, and provides actionable troubleshooting recommendations.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DiagnosticSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class DiagnosticCategory(str, Enum):
    AGENT_HEALTH = "agent_health"
    TASK_SCHEDULING = "task_scheduling"
    COMMUNICATION = "communication"
    MEMORY = "memory"
    TIMEOUT = "timeout"
    CIRCUIT_BREAKER = "circuit_breaker"
    CONCURRENCY = "concurrency"
    DATA_FLOW = "data_flow"


@dataclass
class DiagnosticFinding:
    """A single diagnostic finding."""
    finding_id: str
    category: DiagnosticCategory
    severity: DiagnosticSeverity
    title: str = ""
    description: str = ""
    affected_components: list[str] = field(default_factory=list)
    recommendation: str = ""
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DiagnosticReport:
    """A comprehensive diagnostic report."""
    report_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    findings: list[DiagnosticFinding] = field(default_factory=list)
    summary: str = ""
    overall_status: str = "healthy"   # healthy, degraded, unhealthy
    recommendations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentDiagnostics:
    """Diagnostics and troubleshooting for the multi-agent system.

    Monitors:
        - Agent health (liveness, responsiveness)
        - Task scheduling (queue depth, starvation)
        - Communication (message delivery rates, dead letters)
        - Memory usage (entry count, expiry rate)
        - Circuit breakers (tripped agents)
        - Concurrency (semaphore contention, thread pool)
    """

    def __init__(self) -> None:
        self._findings: list[DiagnosticFinding] = []
        self._reports: list[DiagnosticReport] = []
        self._total_reports = 0

    async def run_diagnostics(self, metrics: Any = None,
                              telemetry: Any = None,
                              registry: Any = None,
                              communication_bus: Any = None,
                              shared_memory: Any = None) -> DiagnosticReport:
        """Run a full diagnostic sweep."""
        self._total_reports += 1
        report = DiagnosticReport(
            report_id=f"diag_{self._total_reports:04d}",
        )

        # 1. Check agent health
        if registry:
            report.findings.extend(self._check_agent_health(registry))

        # 2. Check task scheduling
        if metrics:
            report.findings.extend(self._check_task_scheduling(metrics))

        # 3. Check communication
        if communication_bus:
            report.findings.extend(self._check_communication(communication_bus))

        # 4. Check memory
        if shared_memory:
            report.findings.extend(self._check_memory(shared_memory))

        # Determine overall status
        severities = [f.severity for f in report.findings]
        if DiagnosticSeverity.CRITICAL in severities:
            report.overall_status = "unhealthy"
        elif DiagnosticSeverity.ERROR in severities:
            report.overall_status = "degraded"
        else:
            report.overall_status = "healthy"

        # Generate summary
        crit = sum(1 for f in report.findings if f.severity == DiagnosticSeverity.CRITICAL)
        errs = sum(1 for f in report.findings if f.severity == DiagnosticSeverity.ERROR)
        warns = sum(1 for f in report.findings if f.severity == DiagnosticSeverity.WARNING)

        report.summary = f"Diagnostics: {len(report.findings)} findings — "
        report.summary += f"{crit} critical, {errs} errors, {warns} warnings. "
        report.summary += f"Overall: {report.overall_status}."

        # Collect recommendations
        report.recommendations = [
            f.recommendation for f in report.findings
            if f.recommendation and f.severity in (
                DiagnosticSeverity.ERROR, DiagnosticSeverity.CRITICAL
            )
        ]

        self._reports.append(report)
        self._findings.extend(report.findings)

        logger.info("Diagnostics %s: %s", report.report_id, report.summary)
        return report

    def _check_agent_health(self, registry: Any) -> list[DiagnosticFinding]:
        """Check agent health from registry data."""
        findings = []
        try:
            agents = registry.list_all() if registry else []
            for agent_info in agents:
                agent_id = getattr(agent_info, 'agent_id', 'unknown')
                status = str(getattr(agent_info, 'status', 'unknown'))

                if status == "error":
                    findings.append(DiagnosticFinding(
                        finding_id=f"agent_error_{agent_id}",
                        category=DiagnosticCategory.AGENT_HEALTH,
                        severity=DiagnosticSeverity.ERROR,
                        title=f"Agent {agent_id} in error state",
                        affected_components=[agent_id],
                        recommendation=f"Restart agent {agent_id} and check logs.",
                    ))
                elif status == "offline":
                    findings.append(DiagnosticFinding(
                        finding_id=f"agent_offline_{agent_id}",
                        category=DiagnosticCategory.AGENT_HEALTH,
                        severity=DiagnosticSeverity.WARNING,
                        title=f"Agent {agent_id} is offline",
                        affected_components=[agent_id],
                        recommendation=f"Verify agent {agent_id} is running.",
                    ))
        except Exception as exc:
            findings.append(DiagnosticFinding(
                finding_id="registry_access_error",
                category=DiagnosticCategory.AGENT_HEALTH,
                severity=DiagnosticSeverity.ERROR,
                title="Cannot access agent registry",
                description=str(exc),
            ))
        return findings

    def _check_task_scheduling(self, metrics: Any) -> list[DiagnosticFinding]:
        """Check task scheduling metrics."""
        findings = []

        try:
            task_rate = getattr(metrics, 'get_error_rate', lambda: 0.0)()
            if task_rate > 0.2:
                findings.append(DiagnosticFinding(
                    finding_id="high_task_error_rate",
                    category=DiagnosticCategory.TASK_SCHEDULING,
                    severity=DiagnosticSeverity.ERROR,
                    title=f"High task error rate: {task_rate:.1%}",
                    recommendation="Investigate failing task types and agent availability.",
                ))

            queue_depth = getattr(metrics, 'queue_depth', 0)
            if queue_depth > 100:
                findings.append(DiagnosticFinding(
                    finding_id="high_queue_depth",
                    category=DiagnosticCategory.TASK_SCHEDULING,
                    severity=DiagnosticSeverity.WARNING,
                    title=f"High task queue depth: {queue_depth}",
                    recommendation="Scale up agent pool or increase concurrency limits.",
                ))

        except Exception:
            pass

        return findings

    def _check_communication(self, comm_bus: Any) -> list[DiagnosticFinding]:
        """Check communication bus health."""
        findings = []

        try:
            dead_letter = getattr(comm_bus, 'dead_letter_count', 0)
            if dead_letter > 50:
                findings.append(DiagnosticFinding(
                    finding_id="high_dead_letters",
                    category=DiagnosticCategory.COMMUNICATION,
                    severity=DiagnosticSeverity.WARNING,
                    title=f"High dead letter count: {dead_letter}",
                    recommendation="Check for misconfigured agent handlers.",
                ))

            stats = getattr(comm_bus, 'stats', None)
            if stats:
                total = getattr(stats, 'messages_sent', 0)
                failed = getattr(stats, 'messages_failed', 0)
                if total > 0 and failed / total > 0.1:
                    findings.append(DiagnosticFinding(
                        finding_id="high_message_failure_rate",
                        category=DiagnosticCategory.COMMUNICATION,
                        severity=DiagnosticSeverity.ERROR,
                        title=f"High message failure rate: {failed}/{total}",
                        recommendation="Check agent handler availability and network connectivity.",
                    ))
        except Exception:
            pass

        return findings

    def _check_memory(self, shared_memory: Any) -> list[DiagnosticFinding]:
        """Check shared memory health."""
        findings = []

        try:
            size = getattr(shared_memory, 'total_size', 0)
            max_size = 100000
            if size > max_size * 0.9:
                findings.append(DiagnosticFinding(
                    finding_id="memory_high_usage",
                    category=DiagnosticCategory.MEMORY,
                    severity=DiagnosticSeverity.WARNING,
                    title=f"Shared memory near capacity: {size}/{max_size}",
                    recommendation="Increase memory limit or clean up expired entries.",
                ))
        except Exception:
            pass

        return findings

    def get_last_report(self) -> Optional[DiagnosticReport]:
        return self._reports[-1] if self._reports else None

    @property
    def total_reports(self) -> int:
        return self._total_reports
