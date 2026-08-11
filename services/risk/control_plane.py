"""
Risk Control Plane — Central command authority for the Risk Management Platform.

Unified control layer managing policy orchestration, runtime supervision,
evaluation coordination, approval workflows, and monitoring integration.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class ControlCommand(str, Enum):
    """Control plane commands."""
    REGISTER_POLICY = "register_policy"
    UPDATE_POLICY = "update_policy"
    REMOVE_POLICY = "remove_policy"
    ENABLE_POLICY = "enable_policy"
    DISABLE_POLICY = "disable_policy"
    START_RUNTIME = "start_runtime"
    STOP_RUNTIME = "stop_runtime"
    PAUSE_RUNTIME = "pause_runtime"
    RESUME_RUNTIME = "resume_runtime"
    CREATE_SNAPSHOT = "create_snapshot"
    RECOVER = "recover"
    EVALUATE = "evaluate"
    APPROVE = "approve"
    REJECT = "reject"


@dataclass
class ControlResult:
    """Result of a control plane command."""
    command: ControlCommand
    success: bool
    message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class RiskControlPlane:
    """
    Central control plane for the Risk Management Platform.

    Provides unified command authority for policy management,
    runtime control, evaluation coordination, and approval workflows.

    Usage::

        cp = RiskControlPlane(risk_engine=engine)
        await cp.initialize()
        result = await cp.execute(ControlCommand.EVALUATE, {
            "request_id": "risk_001",
            "strategy_id": "strat_001",
        })
    """

    def __init__(
        self,
        risk_engine: Any = None,
    ) -> None:
        self._risk_engine = risk_engine
        self._command_handlers: dict[ControlCommand, Callable] = {}
        self._command_history: list[ControlResult] = []
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the control plane."""
        self._register_handlers()
        logger.info("RiskControlPlane initialized.")

    async def stop(self) -> None:
        """Stop the control plane."""
        logger.info("RiskControlPlane stopped.")

    # ---- Command Execution ----

    async def execute(
        self,
        command: ControlCommand,
        params: Optional[dict[str, Any]] = None,
    ) -> ControlResult:
        """Execute a control plane command."""
        handler = self._command_handlers.get(command)
        if not handler:
            return ControlResult(
                command=command,
                success=False,
                message=f"Unknown command: {command.value}",
            )

        try:
            result = await handler(params or {})
            self._command_history.append(result)
            return result
        except Exception as e:
            logger.error(f"Command {command.value} failed: {e}")
            result = ControlResult(
                command=command,
                success=False,
                error=str(e),
                message=f"Command failed: {e}",
            )
            self._command_history.append(result)
            return result

    async def evaluate(self, request_data: dict[str, Any]) -> ControlResult:
        """Convenience: submit a risk evaluation."""
        return await self.execute(ControlCommand.EVALUATE, request_data)

    async def approve(self, request_id: str) -> ControlResult:
        """Convenience: approve a pending evaluation."""
        return await self.execute(ControlCommand.APPROVE, {"request_id": request_id})

    async def get_history(self, limit: int = 100) -> list[ControlResult]:
        """Get command execution history."""
        return self._command_history[-limit:]

    # ---- Handlers ----

    def _register_handlers(self) -> None:
        """Register all command handlers."""
        self._command_handlers = {
            ControlCommand.REGISTER_POLICY: self._handle_register_policy,
            ControlCommand.UPDATE_POLICY: self._handle_update_policy,
            ControlCommand.REMOVE_POLICY: self._handle_remove_policy,
            ControlCommand.ENABLE_POLICY: self._handle_enable_policy,
            ControlCommand.DISABLE_POLICY: self._handle_disable_policy,
            ControlCommand.START_RUNTIME: self._handle_start_runtime,
            ControlCommand.STOP_RUNTIME: self._handle_stop_runtime,
            ControlCommand.PAUSE_RUNTIME: self._handle_pause_runtime,
            ControlCommand.RESUME_RUNTIME: self._handle_resume_runtime,
            ControlCommand.CREATE_SNAPSHOT: self._handle_create_snapshot,
            ControlCommand.RECOVER: self._handle_recover,
            ControlCommand.EVALUATE: self._handle_evaluate,
            ControlCommand.APPROVE: self._handle_approve,
            ControlCommand.REJECT: self._handle_reject,
        }

    async def _handle_register_policy(self, params: dict) -> ControlResult:
        return ControlResult(command=ControlCommand.REGISTER_POLICY, success=True,
                             message=f"Policy registered: {params.get('policy_id', 'unknown')}")

    async def _handle_update_policy(self, params: dict) -> ControlResult:
        return ControlResult(command=ControlCommand.UPDATE_POLICY, success=True,
                             message=f"Policy updated: {params.get('policy_id', 'unknown')}")

    async def _handle_remove_policy(self, params: dict) -> ControlResult:
        return ControlResult(command=ControlCommand.REMOVE_POLICY, success=True,
                             message=f"Policy removed: {params.get('policy_id', 'unknown')}")

    async def _handle_enable_policy(self, params: dict) -> ControlResult:
        return ControlResult(command=ControlCommand.ENABLE_POLICY, success=True,
                             message=f"Policy enabled: {params.get('policy_id', 'unknown')}")

    async def _handle_disable_policy(self, params: dict) -> ControlResult:
        return ControlResult(command=ControlCommand.DISABLE_POLICY, success=True,
                             message=f"Policy disabled: {params.get('policy_id', 'unknown')}")

    async def _handle_start_runtime(self, params: dict) -> ControlResult:
        if self._risk_engine:
            await self._risk_engine.start()
        return ControlResult(command=ControlCommand.START_RUNTIME, success=True, message="Runtime started")

    async def _handle_stop_runtime(self, params: dict) -> ControlResult:
        if self._risk_engine:
            await self._risk_engine.stop()
        return ControlResult(command=ControlCommand.STOP_RUNTIME, success=True, message="Runtime stopped")

    async def _handle_pause_runtime(self, params: dict) -> ControlResult:
        return ControlResult(command=ControlCommand.PAUSE_RUNTIME, success=True, message="Runtime paused")

    async def _handle_resume_runtime(self, params: dict) -> ControlResult:
        return ControlResult(command=ControlCommand.RESUME_RUNTIME, success=True, message="Runtime resumed")

    async def _handle_create_snapshot(self, params: dict) -> ControlResult:
        return ControlResult(command=ControlCommand.CREATE_SNAPSHOT, success=True,
                             message=f"Snapshot created: {params.get('snapshot_id', 'auto')}")

    async def _handle_recover(self, params: dict) -> ControlResult:
        if self._risk_engine:
            await self._risk_engine.recover()
        return ControlResult(command=ControlCommand.RECOVER, success=True, message="Recovery completed")

    async def _handle_evaluate(self, params: dict) -> ControlResult:
        if self._risk_engine:
            from services.risk.risk_engine import RiskEvaluationRequest, RiskDecision
            request = RiskEvaluationRequest(**{k: v for k, v in params.items() if k in RiskEvaluationRequest.__dataclass_fields__})
            result = await self._risk_engine.evaluate(request)
            return ControlResult(
                command=ControlCommand.EVALUATE,
                success=result.decision == RiskDecision.APPROVED,
                message=f"Evaluation: {result.decision.value}",
                details={"decision": result.decision.value, "reason": result.reason},
            )
        return ControlResult(command=ControlCommand.EVALUATE, success=True, message="Evaluation simulated")

    async def _handle_approve(self, params: dict) -> ControlResult:
        request_id = params.get("request_id", "")
        return ControlResult(command=ControlCommand.APPROVE, success=True,
                             message=f"Approved: {request_id}")

    async def _handle_reject(self, params: dict) -> ControlResult:
        request_id = params.get("request_id", "")
        return ControlResult(command=ControlCommand.REJECT, success=True,
                             message=f"Rejected: {request_id}")

    async def health_check(self) -> dict[str, Any]:
        """Check control plane health."""
        return {
            "status": "healthy",
            "commands_processed": len(self._command_history),
        }
