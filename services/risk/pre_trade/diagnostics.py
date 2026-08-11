"""
Pre-Trade Diagnostics — System diagnostics for the pre-trade risk pipeline.

Provides comprehensive health checks across all pre-trade components:
engine, runtime, rule chain, checkers, and approval workflow.
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
    """Diagnostic check result status."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


@dataclass
class DiagnosticCheck:
    """Result of a single diagnostic check."""
    name: str
    status: DiagnosticStatus = DiagnosticStatus.UNKNOWN
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DiagnosticReport:
    """Aggregate diagnostic report for the pre-trade pipeline."""
    overall_status: DiagnosticStatus = DiagnosticStatus.UNKNOWN
    checks: list[DiagnosticCheck] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PreTradeDiagnostics:
    """
    System diagnostics for the Pre-Trade Risk Platform.

    Runs comprehensive checks across all subsystems and produces
    a diagnostic report for monitoring and troubleshooting.

    Usage::

        diag = PreTradeDiagnostics(engine=engine, runtime=runtime, rule_chain=chain)
        report = await diag.run()
    """

    def __init__(
        self,
        engine: Optional[Any] = None,
        runtime: Optional[Any] = None,
        rule_chain: Optional[Any] = None,
        approval_workflow: Optional[Any] = None,
    ) -> None:
        self._engine = engine
        self._runtime = runtime
        self._rule_chain = rule_chain
        self._approval_workflow = approval_workflow

    async def run(self) -> DiagnosticReport:
        """Run all diagnostic checks and return a report."""
        checks: list[DiagnosticCheck] = []

        # Engine check
        checks.append(await self._check_engine())

        # Runtime check
        checks.append(await self._check_runtime())

        # Rule chain check
        checks.append(await self._check_rule_chain())

        # Approval workflow check
        checks.append(await self._check_approval_workflow())

        # Pipeline integrity
        checks.append(await self._check_pipeline_integrity())

        # Determine overall status
        statuses = [c.status for c in checks]
        if DiagnosticStatus.UNHEALTHY in statuses:
            overall = DiagnosticStatus.UNHEALTHY
        elif DiagnosticStatus.DEGRADED in statuses:
            overall = DiagnosticStatus.DEGRADED
        elif all(s == DiagnosticStatus.HEALTHY for s in statuses):
            overall = DiagnosticStatus.HEALTHY
        else:
            overall = DiagnosticStatus.UNKNOWN

        return DiagnosticReport(overall_status=overall, checks=checks)

    async def _check_engine(self) -> DiagnosticCheck:
        """Check PreTradeRiskEngine health."""
        if not self._engine:
            return DiagnosticCheck(
                name="pre_trade_engine",
                status=DiagnosticStatus.UNKNOWN,
                message="Engine not connected.",
            )
        try:
            stats = await self._engine.get_stats()
            return DiagnosticCheck(
                name="pre_trade_engine",
                status=DiagnosticStatus.HEALTHY,
                message="Engine is operational.",
                details=stats,
            )
        except Exception as e:
            return DiagnosticCheck(
                name="pre_trade_engine",
                status=DiagnosticStatus.UNHEALTHY,
                message=f"Engine check failed: {e}",
            )

    async def _check_runtime(self) -> DiagnosticCheck:
        """Check PreTradeRuntime health."""
        if not self._runtime:
            return DiagnosticCheck(
                name="pre_trade_runtime",
                status=DiagnosticStatus.UNKNOWN,
                message="Runtime not connected.",
            )
        try:
            health = await self._runtime.health_check()
            status = (
                DiagnosticStatus.HEALTHY
                if health.get("status") == "running"
                else DiagnosticStatus.DEGRADED
            )
            return DiagnosticCheck(
                name="pre_trade_runtime",
                status=status,
                message=f"Runtime status: {health.get('status')}",
                details=health,
            )
        except Exception as e:
            return DiagnosticCheck(
                name="pre_trade_runtime",
                status=DiagnosticStatus.UNHEALTHY,
                message=f"Runtime check failed: {e}",
            )

    async def _check_rule_chain(self) -> DiagnosticCheck:
        """Check RiskRuleChain health."""
        if not self._rule_chain:
            return DiagnosticCheck(
                name="rule_chain",
                status=DiagnosticStatus.UNKNOWN,
                message="Rule chain not connected.",
            )
        try:
            stats = self._rule_chain.get_stats()
            checker_count = stats.get("checker_count", 0)
            enabled_count = stats.get("enabled_count", 0)
            status = (
                DiagnosticStatus.HEALTHY if enabled_count > 0
                else DiagnosticStatus.DEGRADED
            )
            return DiagnosticCheck(
                name="rule_chain",
                status=status,
                message=f"{enabled_count}/{checker_count} checkers enabled.",
                details=stats,
            )
        except Exception as e:
            return DiagnosticCheck(
                name="rule_chain",
                status=DiagnosticStatus.UNHEALTHY,
                message=f"Rule chain check failed: {e}",
            )

    async def _check_approval_workflow(self) -> DiagnosticCheck:
        """Check ApprovalWorkflow health."""
        if not self._approval_workflow:
            return DiagnosticCheck(
                name="approval_workflow",
                status=DiagnosticStatus.UNKNOWN,
                message="Approval workflow not connected.",
            )
        try:
            pending = await self._approval_workflow.get_pending()
            return DiagnosticCheck(
                name="approval_workflow",
                status=DiagnosticStatus.HEALTHY,
                message=f"Approval workflow operational. {len(pending)} pending.",
                details={"pending_count": len(pending)},
            )
        except Exception as e:
            return DiagnosticCheck(
                name="approval_workflow",
                status=DiagnosticStatus.UNHEALTHY,
                message=f"Approval workflow check failed: {e}",
            )

    async def _check_pipeline_integrity(self) -> DiagnosticCheck:
        """Verify end-to-end pipeline connectivity."""
        checks_passed = 0
        checks_total = 0

        if self._engine:
            checks_total += 1
            if hasattr(self._engine, "evaluate"):
                checks_passed += 1

        if self._runtime:
            checks_total += 1
            if hasattr(self._runtime, "health_check"):
                checks_passed += 1

        if self._rule_chain:
            checks_total += 1
            if hasattr(self._rule_chain, "execute"):
                checks_passed += 1

        status = DiagnosticStatus.HEALTHY if checks_passed == checks_total else DiagnosticStatus.DEGRADED
        return DiagnosticCheck(
            name="pipeline_integrity",
            status=status,
            message=f"Pipeline integrity: {checks_passed}/{checks_total} components connected.",
            details={
                "components_connected": checks_passed,
                "components_total": checks_total,
            },
        )
