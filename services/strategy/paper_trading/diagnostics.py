"""
Paper Trading Diagnostics
=========================
Diagnostic analysis for the paper trading platform.

Checks:
    - PaperTradingEngine health
    - VirtualExchange readiness
    - VirtualOMS order flow
    - ExecutionSimulator pipeline integrity
    - KillSwitch configuration
    - Session consistency
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PTDiagnosticSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"
    OK = "OK"


@dataclass
class PTDiagnosticIssue:
    category: str
    severity: PTDiagnosticSeverity
    message: str
    detail: Optional[str] = None
    recommendation: Optional[str] = None


@dataclass
class PTDiagnosticReport:
    report_id: str = ""
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    overall_status: PTDiagnosticSeverity = PTDiagnosticSeverity.OK
    issues: List[PTDiagnosticIssue] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == PTDiagnosticSeverity.CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == PTDiagnosticSeverity.WARNING)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at.isoformat(),
            "overall_status": self.overall_status.value,
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
            "total_issues": len(self.issues),
            "issues": [
                {"category": i.category, "severity": i.severity.value,
                 "message": i.message, "detail": i.detail,
                 "recommendation": i.recommendation}
                for i in self.issues
            ],
            "metrics": self.metrics,
        }


class PaperTradingDiagnostics:
    """Diagnostic analyzer for the paper trading platform."""

    def __init__(self):
        self._engine: Optional[Any] = None
        self._virtual_exchange: Optional[Any] = None
        self._virtual_oms: Optional[Any] = None
        self._virtual_portfolio: Optional[Any] = None
        self._virtual_account: Optional[Any] = None
        self._execution_simulator: Optional[Any] = None
        self._kill_switch: Optional[Any] = None
        self._performance_evaluator: Optional[Any] = None
        self._promotion_workflow: Optional[Any] = None

    def wire(self, **kwargs: Any) -> None:
        for name, component in kwargs.items():
            if hasattr(self, f"_{name}"):
                setattr(self, f"_{name}", component)
        logger.info("PaperTradingDiagnostics wired")

    async def run_full_diagnostics(self) -> PTDiagnosticReport:
        import uuid
        report = PTDiagnosticReport(report_id=f"ptdiag_{uuid.uuid4().hex[:8]}")

        checks = [
            self._check_engine,
            self._check_virtual_exchange,
            self._check_virtual_oms,
            self._check_virtual_portfolio,
            self._check_virtual_account,
            self._check_execution_simulator,
            self._check_kill_switch,
            self._check_performance_evaluator,
            self._check_promotion_workflow,
            self._check_pipeline_integrity,
        ]

        for check in checks:
            issues = await check()
            report.issues.extend(issues)

        if any(i.severity == PTDiagnosticSeverity.CRITICAL for i in report.issues):
            report.overall_status = PTDiagnosticSeverity.CRITICAL
        elif any(i.severity == PTDiagnosticSeverity.WARNING for i in report.issues):
            report.overall_status = PTDiagnosticSeverity.WARNING

        return report

    async def _check_engine(self) -> List[PTDiagnosticIssue]:
        if not self._engine:
            return [PTDiagnosticIssue("paper_engine", PTDiagnosticSeverity.CRITICAL,
                                      "PaperTradingEngine not wired")]
        if not self._engine.is_initialized:
            return [PTDiagnosticIssue("paper_engine", PTDiagnosticSeverity.CRITICAL,
                                      "PaperTradingEngine not initialized")]
        return [PTDiagnosticIssue("paper_engine", PTDiagnosticSeverity.OK,
                                  "PaperTradingEngine healthy")]

    async def _check_virtual_exchange(self) -> List[PTDiagnosticIssue]:
        if not self._virtual_exchange:
            return [PTDiagnosticIssue("virtual_exchange", PTDiagnosticSeverity.WARNING,
                                      "VirtualExchange not wired")]
        if not self._virtual_exchange.is_initialized:
            return [PTDiagnosticIssue("virtual_exchange", PTDiagnosticSeverity.CRITICAL,
                                      "VirtualExchange not initialized")]
        return [PTDiagnosticIssue("virtual_exchange", PTDiagnosticSeverity.OK,
                                  "VirtualExchange operational")]

    async def _check_virtual_oms(self) -> List[PTDiagnosticIssue]:
        if not self._virtual_oms:
            return [PTDiagnosticIssue("virtual_oms", PTDiagnosticSeverity.WARNING,
                                      "VirtualOMS not wired")]
        if not self._virtual_oms.is_initialized:
            return [PTDiagnosticIssue("virtual_oms", PTDiagnosticSeverity.CRITICAL,
                                      "VirtualOMS not initialized")]
        return [PTDiagnosticIssue("virtual_oms", PTDiagnosticSeverity.OK,
                                  "VirtualOMS operational")]

    async def _check_virtual_portfolio(self) -> List[PTDiagnosticIssue]:
        if not self._virtual_portfolio:
            return [PTDiagnosticIssue("virtual_portfolio", PTDiagnosticSeverity.WARNING,
                                      "VirtualPortfolio not wired")]
        if not self._virtual_portfolio.is_initialized:
            return [PTDiagnosticIssue("virtual_portfolio", PTDiagnosticSeverity.CRITICAL,
                                      "VirtualPortfolio not initialized")]
        return [PTDiagnosticIssue("virtual_portfolio", PTDiagnosticSeverity.OK,
                                  "VirtualPortfolio operational")]

    async def _check_virtual_account(self) -> List[PTDiagnosticIssue]:
        if not self._virtual_account:
            return []
        if not self._virtual_account.is_initialized:
            return [PTDiagnosticIssue("virtual_account", PTDiagnosticSeverity.WARNING,
                                      "VirtualAccount not initialized")]
        return [PTDiagnosticIssue("virtual_account", PTDiagnosticSeverity.OK,
                                  "VirtualAccount operational")]

    async def _check_execution_simulator(self) -> List[PTDiagnosticIssue]:
        if not self._execution_simulator:
            return [PTDiagnosticIssue("execution_simulator", PTDiagnosticSeverity.WARNING,
                                      "ExecutionSimulator not wired")]
        if not self._execution_simulator.is_initialized:
            return [PTDiagnosticIssue("execution_simulator", PTDiagnosticSeverity.CRITICAL,
                                      "ExecutionSimulator not initialized")]
        return [PTDiagnosticIssue("execution_simulator", PTDiagnosticSeverity.OK,
                                  "ExecutionSimulator operational")]

    async def _check_kill_switch(self) -> List[PTDiagnosticIssue]:
        if not self._kill_switch:
            return [PTDiagnosticIssue("kill_switch", PTDiagnosticSeverity.WARNING,
                                      "KillSwitch not wired — risk controls inactive")]
        if not self._kill_switch.is_initialized:
            return [PTDiagnosticIssue("kill_switch", PTDiagnosticSeverity.CRITICAL,
                                      "KillSwitch not initialized")]
        active = self._kill_switch.triggered_strategies()
        if active:
            return [PTDiagnosticIssue("kill_switch", PTDiagnosticSeverity.WARNING,
                                      f"Kill switch active for {len(active)} strategies",
                                      detail=f"Strategies: {active}",
                                      recommendation="Review and reset if appropriate")]
        return [PTDiagnosticIssue("kill_switch", PTDiagnosticSeverity.OK,
                                  "KillSwitch operational, no active triggers")]

    async def _check_performance_evaluator(self) -> List[PTDiagnosticIssue]:
        if not self._performance_evaluator:
            return [PTDiagnosticIssue("performance", PTDiagnosticSeverity.WARNING,
                                      "PerformanceEvaluator not wired")]
        return [PTDiagnosticIssue("performance", PTDiagnosticSeverity.OK,
                                  "PerformanceEvaluator available")]

    async def _check_promotion_workflow(self) -> List[PTDiagnosticIssue]:
        if not self._promotion_workflow:
            return [PTDiagnosticIssue("promotion", PTDiagnosticSeverity.WARNING,
                                      "PromotionWorkflow not wired")]
        return [PTDiagnosticIssue("promotion", PTDiagnosticSeverity.OK,
                                  "PromotionWorkflow available")]

    async def _check_pipeline_integrity(self) -> List[PTDiagnosticIssue]:
        missing = []
        if not self._engine:
            missing.append("PaperTradingEngine")
        if not self._virtual_exchange:
            missing.append("VirtualExchange")
        if not self._virtual_oms:
            missing.append("VirtualOMS")
        if not self._execution_simulator:
            missing.append("ExecutionSimulator")

        if missing:
            return [PTDiagnosticIssue(
                "pipeline", PTDiagnosticSeverity.WARNING,
                f"Incomplete pipeline: missing {', '.join(missing)}",
                recommendation="Wire all required components",
            )]
        return [PTDiagnosticIssue("pipeline", PTDiagnosticSeverity.OK,
                                  "Full pipeline: Engine → Exchange → OMS → Execution — ALL PRESENT")]
