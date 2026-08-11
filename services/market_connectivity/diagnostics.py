"""
Connectivity Diagnostics — Diagnostic analysis for the Market Connectivity
Platform covering all subsystems including runtime, connections, sessions,
protocols, authentication, and health.
"""

from __future__ import annotations

import asyncio
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
    name: str
    category: str
    status: DiagnosticStatus
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ConnectivityDiagnosticReport:
    platform_id: str = "icyquant-connectivity"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    overall_status: DiagnosticStatus = DiagnosticStatus.PASS
    checks: list[DiagnosticCheck] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=lambda: {"pass": 0, "warn": 0, "fail": 0, "skipped": 0})
    recommendations: list[str] = field(default_factory=list)


class ConnectivityDiagnostics:
    """
    Diagnostic analysis for the Market Connectivity Platform.

    Checks all platform subsystems: connections, sessions, protocols,
    authentication, health monitors, and endpoint discovery.

    Usage::

        diag = ConnectivityDiagnostics()
        await diag.initialize()
        report = await diag.run_full_diagnostics()
    """

    SUBSYSTEMS = [
        "connection_runtime",
        "session_management",
        "protocol_layer",
        "authentication",
        "heartbeat_monitor",
        "reconnect_manager",
        "endpoint_discovery",
        "failover_manager",
    ]

    def __init__(self) -> None:
        self._checks: list[DiagnosticCheck] = []
        self._injectables: dict[str, Any] = {}

    async def initialize(self) -> None:
        """Initialize diagnostics."""
        logger.info("ConnectivityDiagnostics initialized.")

    async def stop(self) -> None:
        """Stop diagnostics."""
        logger.info("ConnectivityDiagnostics stopped.")

    def inject(self, name: str, component: Any) -> None:
        """Inject a component for diagnostic checking."""
        self._injectables[name] = component

    # ---- Diagnostic Methods ----

    async def check_connections(self) -> list[DiagnosticCheck]:
        """Check connection health across all exchanges."""
        start = time.monotonic()
        checks: list[DiagnosticCheck] = []
        try:
            connection_manager = self._injectables.get("connection_manager")
            if connection_manager:
                summary = await connection_manager.get_summary()
                checks.append(DiagnosticCheck(
                    name="connection_count",
                    category="connections",
                    status=DiagnosticStatus.PASS if summary["connected"] > 0 else DiagnosticStatus.WARN,
                    message=f"Connected: {summary['connected']}/{summary['total_connections']}",
                    details=summary,
                    duration_ms=(time.monotonic() - start) * 1000,
                ))
            else:
                checks.append(DiagnosticCheck(
                    name="connection_count",
                    category="connections",
                    status=DiagnosticStatus.SKIPPED,
                    message="ConnectionManager not injected",
                    duration_ms=(time.monotonic() - start) * 1000,
                ))
        except Exception as e:
            checks.append(DiagnosticCheck(
                name="connection_count",
                category="connections",
                status=DiagnosticStatus.FAIL,
                message=str(e),
                duration_ms=(time.monotonic() - start) * 1000,
            ))
        return checks

    async def check_sessions(self) -> list[DiagnosticCheck]:
        """Check session health."""
        start = time.monotonic()
        checks: list[DiagnosticCheck] = []
        try:
            session_pool = self._injectables.get("session_pool")
            if session_pool:
                status = await session_pool.get_status()
                checks.append(DiagnosticCheck(
                    name="session_pool_status",
                    category="sessions",
                    status=DiagnosticStatus.PASS if status["total_available"] > 0 else DiagnosticStatus.WARN,
                    message=f"Sessions: {status['total_available']} available, {status['total_in_use']} in use",
                    details=status,
                    duration_ms=(time.monotonic() - start) * 1000,
                ))
            else:
                checks.append(DiagnosticCheck(
                    name="session_pool_status",
                    category="sessions",
                    status=DiagnosticStatus.SKIPPED,
                    message="SessionPool not injected",
                    duration_ms=(time.monotonic() - start) * 1000,
                ))
        except Exception as e:
            checks.append(DiagnosticCheck(
                name="session_pool_status",
                category="sessions",
                status=DiagnosticStatus.FAIL,
                message=str(e),
                duration_ms=(time.monotonic() - start) * 1000,
            ))
        return checks

    async def check_protocols(self) -> list[DiagnosticCheck]:
        """Check protocol layer health."""
        start = time.monotonic()
        checks: list[DiagnosticCheck] = []
        try:
            protocol_manager = self._injectables.get("protocol_manager")
            if protocol_manager:
                protocols = protocol_manager.list_protocols()
                instance_counts = await protocol_manager.get_instance_count()
                checks.append(DiagnosticCheck(
                    name="protocol_registry",
                    category="protocols",
                    status=DiagnosticStatus.PASS if protocols else DiagnosticStatus.FAIL,
                    message=f"Registered: {protocols}, Instances: {instance_counts}",
                    details={"protocols": protocols, "instances": instance_counts},
                    duration_ms=(time.monotonic() - start) * 1000,
                ))
            else:
                checks.append(DiagnosticCheck(
                    name="protocol_registry",
                    category="protocols",
                    status=DiagnosticStatus.SKIPPED,
                    message="ProtocolManager not injected",
                    duration_ms=(time.monotonic() - start) * 1000,
                ))
        except Exception as e:
            checks.append(DiagnosticCheck(
                name="protocol_registry",
                category="protocols",
                status=DiagnosticStatus.FAIL,
                message=str(e),
                duration_ms=(time.monotonic() - start) * 1000,
            ))
        return checks

    async def check_authentication(self) -> list[DiagnosticCheck]:
        """Check authentication framework health."""
        start = time.monotonic()
        checks: list[DiagnosticCheck] = []
        try:
            credential_manager = self._injectables.get("credential_manager")
            if credential_manager:
                summary = await credential_manager.get_summary()
                status = DiagnosticStatus.PASS if summary["active"] > 0 else DiagnosticStatus.WARN
                checks.append(DiagnosticCheck(
                    name="credential_status",
                    category="authentication",
                    status=status,
                    message=f"Active credentials: {summary['active']}",
                    details=summary,
                    duration_ms=(time.monotonic() - start) * 1000,
                ))
            else:
                checks.append(DiagnosticCheck(
                    name="credential_status",
                    category="authentication",
                    status=DiagnosticStatus.SKIPPED,
                    message="CredentialManager not injected",
                    duration_ms=(time.monotonic() - start) * 1000,
                ))
        except Exception as e:
            checks.append(DiagnosticCheck(
                name="credential_status",
                category="authentication",
                status=DiagnosticStatus.FAIL,
                message=str(e),
                duration_ms=(time.monotonic() - start) * 1000,
            ))
        return checks

    async def check_heartbeat(self) -> list[DiagnosticCheck]:
        """Check heartbeat monitor health."""
        start = time.monotonic()
        checks: list[DiagnosticCheck] = []
        try:
            heartbeat_monitor = self._injectables.get("heartbeat_monitor")
            if heartbeat_monitor:
                summary = await heartbeat_monitor.get_summary()
                dead = summary.get("dead", 0)
                status = DiagnosticStatus.PASS if dead == 0 else DiagnosticStatus.FAIL
                checks.append(DiagnosticCheck(
                    name="heartbeat_status",
                    category="heartbeat",
                    status=status,
                    message=f"Alive: {summary.get('alive', 0)}, Dead: {dead}",
                    details=summary,
                    duration_ms=(time.monotonic() - start) * 1000,
                ))
            else:
                checks.append(DiagnosticCheck(
                    name="heartbeat_status",
                    category="heartbeat",
                    status=DiagnosticStatus.SKIPPED,
                    message="HeartbeatMonitor not injected",
                    duration_ms=(time.monotonic() - start) * 1000,
                ))
        except Exception as e:
            checks.append(DiagnosticCheck(
                name="heartbeat_status",
                category="heartbeat",
                status=DiagnosticStatus.FAIL,
                message=str(e),
                duration_ms=(time.monotonic() - start) * 1000,
            ))
        return checks

    # ---- Full Diagnostics ----

    async def run_full_diagnostics(self) -> ConnectivityDiagnosticReport:
        """Run comprehensive diagnostics on all subsystems."""
        report = ConnectivityDiagnosticReport()
        logger.info("Running full connectivity diagnostics...")

        all_checks: list[DiagnosticCheck] = []

        chequers = [
            self.check_connections,
            self.check_sessions,
            self.check_protocols,
            self.check_authentication,
            self.check_heartbeat,
        ]

        for check_fn in chequers:
            try:
                checks = await check_fn()
                all_checks.extend(checks)
            except Exception as e:
                all_checks.append(DiagnosticCheck(
                    name=check_fn.__name__,
                    category="diagnostics",
                    status=DiagnosticStatus.FAIL,
                    message=f"Diagnostic check failed: {e}",
                ))

        report.checks = all_checks

        # Calculate summary
        for check in all_checks:
            report.summary[check.status.value] = report.summary.get(check.status.value, 0) + 1

        # Determine overall status
        if report.summary.get("fail", 0) > 0:
            report.overall_status = DiagnosticStatus.FAIL
        elif report.summary.get("warn", 0) > 0:
            report.overall_status = DiagnosticStatus.WARN
        else:
            report.overall_status = DiagnosticStatus.PASS

        # Generate recommendations
        for check in all_checks:
            if check.status == DiagnosticStatus.FAIL:
                report.recommendations.append(f"[{check.category}] {check.name}: {check.message}")
            elif check.status == DiagnosticStatus.WARN:
                report.recommendations.append(f"[{check.category}] Warning: {check.name}: {check.message}")

        logger.info(
            "Diagnostics complete: %s (pass=%d warn=%d fail=%d)",
            report.overall_status.value,
            report.summary.get("pass", 0),
            report.summary.get("warn", 0),
            report.summary.get("fail", 0),
        )

        return report
