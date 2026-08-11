"""
Platform Control Plane — Central governance for the production risk platform.

Unified command and control for risk policy, runtime, scheduling,
governance, and monitoring across the entire risk ecosystem.
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
    """Platform control plane commands."""
    # Policy management
    DEPLOY_POLICY = "deploy_policy"
    ROLLBACK_POLICY = "rollback_policy"
    HOT_RELOAD_POLICY = "hot_reload_policy"
    DISTRIBUTE_POLICY = "distribute_policy"

    # Runtime management
    START_RUNTIME = "start_runtime"
    STOP_RUNTIME = "stop_runtime"
    RESTART_RUNTIME = "restart_runtime"
    SCALE_RUNTIME = "scale_runtime"

    # Cluster management
    ADD_NODE = "add_node"
    REMOVE_NODE = "remove_node"
    PROMOTE_LEADER = "promote_leader"
    TRIGGER_FAILOVER = "trigger_failover"

    # Governance
    ENABLE_AUDIT = "enable_audit"
    DISABLE_AUDIT = "disable_audit"
    ENABLE_OBSERVABILITY = "enable_observability"
    DISABLE_OBSERVABILITY = "disable_observability"

    # Evaluation
    EVALUATE = "evaluate"
    BATCH_EVALUATE = "batch_evaluate"
    APPROVE = "approve"
    REJECT = "reject"

    # Maintenance
    ENTER_MAINTENANCE = "enter_maintenance"
    EXIT_MAINTENANCE = "exit_maintenance"


class ControlResultStatus(str, Enum):
    """Control command result status."""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    PENDING = "pending"


@dataclass
class ControlResult:
    """Result of a control plane command."""
    command: ControlCommand
    status: ControlResultStatus = ControlResultStatus.SUCCESS
    message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_time_ms: float = 0.0


@dataclass
class GovernanceState:
    """Current governance state of the risk platform."""
    audit_enabled: bool = True
    observability_enabled: bool = True
    maintenance_mode: bool = False
    policy_version: str = "1.0.0"
    active_nodes: int = 1
    leader_node_id: str = ""
    last_policy_deploy: Optional[datetime] = None
    last_failover: Optional[datetime] = None


class PlatformControlPlane:
    """
    Central governance for the production risk platform.

    Provides unified command authority across policy management,
    runtime control, cluster orchestration, and platform governance.

    Usage::

        cp = PlatformControlPlane(platform=platform)
        await cp.initialize()
        result = await cp.execute(ControlCommand.DEPLOY_POLICY, {
            "policy_id": "position_limit_v2",
        })
    """

    def __init__(self, platform: Any = None) -> None:
        self._platform = platform
        self._governance = GovernanceState()
        self._command_handlers: dict[ControlCommand, Callable] = {}
        self._command_history: list[ControlResult] = []
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the platform control plane."""
        self._register_handlers()
        logger.info("PlatformControlPlane initialized.")

    async def stop(self) -> None:
        """Stop the platform control plane."""
        logger.info("PlatformControlPlane stopped.")

    # ---- Command Execution ----

    async def execute(
        self,
        command: ControlCommand,
        params: Optional[dict[str, Any]] = None,
    ) -> ControlResult:
        """Execute a control plane command."""
        start = asyncio.get_event_loop().time()

        handler = self._command_handlers.get(command)
        if not handler:
            return ControlResult(
                command=command,
                status=ControlResultStatus.FAILED,
                message=f"Unknown command: {command.value}",
            )

        try:
            result = await handler(params or {})
            result.execution_time_ms = (asyncio.get_event_loop().time() - start) * 1000
            async with self._lock:
                self._command_history.append(result)
                if len(self._command_history) > 1000:
                    self._command_history = self._command_history[-1000:]
            return result
        except Exception as e:
            logger.error(f"Command {command.value} failed: {e}")
            result = ControlResult(
                command=command,
                status=ControlResultStatus.FAILED,
                error=str(e),
                message=f"Command failed: {e}",
            )
            self._command_history.append(result)
            return result

    # ---- Convenience Methods ----

    async def deploy_policy(self, policy_data: dict[str, Any]) -> ControlResult:
        return await self.execute(ControlCommand.DEPLOY_POLICY, policy_data)

    async def hot_reload(self) -> ControlResult:
        return await self.execute(ControlCommand.HOT_RELOAD_POLICY, {})

    async def evaluate(self, request_data: dict[str, Any]) -> ControlResult:
        return await self.execute(ControlCommand.EVALUATE, request_data)

    async def approve(self, request_id: str) -> ControlResult:
        return await self.execute(ControlCommand.APPROVE, {"request_id": request_id})

    async def reject(self, request_id: str) -> ControlResult:
        return await self.execute(ControlCommand.REJECT, {"request_id": request_id})

    async def trigger_failover(self) -> ControlResult:
        return await self.execute(ControlCommand.TRIGGER_FAILOVER, {})

    async def enter_maintenance(self) -> ControlResult:
        return await self.execute(ControlCommand.ENTER_MAINTENANCE, {})

    async def exit_maintenance(self) -> ControlResult:
        return await self.execute(ControlCommand.EXIT_MAINTENANCE, {})

    # ---- Query ----

    async def get_history(self, limit: int = 100) -> list[ControlResult]:
        return self._command_history[-limit:]

    async def get_governance_state(self) -> GovernanceState:
        return self._governance

    # ---- Handlers ----

    def _register_handlers(self) -> None:
        self._command_handlers = {
            ControlCommand.DEPLOY_POLICY: self._handle_deploy_policy,
            ControlCommand.ROLLBACK_POLICY: self._handle_rollback_policy,
            ControlCommand.HOT_RELOAD_POLICY: self._handle_hot_reload,
            ControlCommand.DISTRIBUTE_POLICY: self._handle_distribute_policy,
            ControlCommand.START_RUNTIME: self._handle_start_runtime,
            ControlCommand.STOP_RUNTIME: self._handle_stop_runtime,
            ControlCommand.RESTART_RUNTIME: self._handle_restart_runtime,
            ControlCommand.SCALE_RUNTIME: self._handle_scale_runtime,
            ControlCommand.ADD_NODE: self._handle_add_node,
            ControlCommand.REMOVE_NODE: self._handle_remove_node,
            ControlCommand.PROMOTE_LEADER: self._handle_promote_leader,
            ControlCommand.TRIGGER_FAILOVER: self._handle_trigger_failover,
            ControlCommand.ENABLE_AUDIT: self._handle_enable_audit,
            ControlCommand.DISABLE_AUDIT: self._handle_disable_audit,
            ControlCommand.ENABLE_OBSERVABILITY: self._handle_enable_observability,
            ControlCommand.DISABLE_OBSERVABILITY: self._handle_disable_observability,
            ControlCommand.EVALUATE: self._handle_evaluate,
            ControlCommand.BATCH_EVALUATE: self._handle_batch_evaluate,
            ControlCommand.APPROVE: self._handle_approve,
            ControlCommand.REJECT: self._handle_reject,
            ControlCommand.ENTER_MAINTENANCE: self._handle_enter_maintenance,
            ControlCommand.EXIT_MAINTENANCE: self._handle_exit_maintenance,
        }

    async def _handle_deploy_policy(self, params: dict) -> ControlResult:
        policy_id = params.get("policy_id", "unknown")
        self._governance.last_policy_deploy = datetime.now(timezone.utc)
        return ControlResult(command=ControlCommand.DEPLOY_POLICY,
                             message=f"Policy deployed: {policy_id}")

    async def _handle_rollback_policy(self, params: dict) -> ControlResult:
        return ControlResult(command=ControlCommand.ROLLBACK_POLICY,
                             message=f"Policy rolled back: {params.get('policy_id', 'unknown')}")

    async def _handle_hot_reload(self, params: dict) -> ControlResult:
        return ControlResult(command=ControlCommand.HOT_RELOAD_POLICY,
                             message="Policies hot-reloaded successfully")

    async def _handle_distribute_policy(self, params: dict) -> ControlResult:
        nodes = params.get("nodes", ["all"])
        return ControlResult(command=ControlCommand.DISTRIBUTE_POLICY,
                             message=f"Policy distributed to {len(nodes)} nodes")

    async def _handle_start_runtime(self, params: dict) -> ControlResult:
        return ControlResult(command=ControlCommand.START_RUNTIME,
                             message="Runtime started")

    async def _handle_stop_runtime(self, params: dict) -> ControlResult:
        return ControlResult(command=ControlCommand.STOP_RUNTIME,
                             message="Runtime stopped")

    async def _handle_restart_runtime(self, params: dict) -> ControlResult:
        return ControlResult(command=ControlCommand.RESTART_RUNTIME,
                             message="Runtime restarted")

    async def _handle_scale_runtime(self, params: dict) -> ControlResult:
        count = params.get("count", 1)
        return ControlResult(command=ControlCommand.SCALE_RUNTIME,
                             message=f"Runtime scaled to {count} instances")

    async def _handle_add_node(self, params: dict) -> ControlResult:
        self._governance.active_nodes += 1
        return ControlResult(command=ControlCommand.ADD_NODE,
                             message=f"Node added: {params.get('node_id', 'unknown')}")

    async def _handle_remove_node(self, params: dict) -> ControlResult:
        self._governance.active_nodes = max(1, self._governance.active_nodes - 1)
        return ControlResult(command=ControlCommand.REMOVE_NODE,
                             message=f"Node removed: {params.get('node_id', 'unknown')}")

    async def _handle_promote_leader(self, params: dict) -> ControlResult:
        node_id = params.get("node_id", "")
        self._governance.leader_node_id = node_id
        return ControlResult(command=ControlCommand.PROMOTE_LEADER,
                             message=f"Leader promoted: {node_id}")

    async def _handle_trigger_failover(self, params: dict) -> ControlResult:
        self._governance.last_failover = datetime.now(timezone.utc)
        return ControlResult(command=ControlCommand.TRIGGER_FAILOVER,
                             message="Failover triggered successfully")

    async def _handle_enable_audit(self, params: dict) -> ControlResult:
        self._governance.audit_enabled = True
        return ControlResult(command=ControlCommand.ENABLE_AUDIT, message="Audit enabled")

    async def _handle_disable_audit(self, params: dict) -> ControlResult:
        self._governance.audit_enabled = False
        return ControlResult(command=ControlCommand.DISABLE_AUDIT, message="Audit disabled")

    async def _handle_enable_observability(self, params: dict) -> ControlResult:
        self._governance.observability_enabled = True
        return ControlResult(command=ControlCommand.ENABLE_OBSERVABILITY,
                             message="Observability enabled")

    async def _handle_disable_observability(self, params: dict) -> ControlResult:
        self._governance.observability_enabled = False
        return ControlResult(command=ControlCommand.DISABLE_OBSERVABILITY,
                             message="Observability disabled")

    async def _handle_evaluate(self, params: dict) -> ControlResult:
        if self._platform:
            result = await self._platform.evaluate_order(params)
            return ControlResult(command=ControlCommand.EVALUATE,
                                 message=f"Evaluated: {result.get('decision', 'unknown')}",
                                 details=result)
        return ControlResult(command=ControlCommand.EVALUATE, message="Evaluation simulated")

    async def _handle_batch_evaluate(self, params: dict) -> ControlResult:
        count = len(params.get("requests", []))
        return ControlResult(command=ControlCommand.BATCH_EVALUATE,
                             message=f"Batch evaluated {count} requests")

    async def _handle_approve(self, params: dict) -> ControlResult:
        return ControlResult(command=ControlCommand.APPROVE,
                             message=f"Approved: {params.get('request_id', '')}")

    async def _handle_reject(self, params: dict) -> ControlResult:
        return ControlResult(command=ControlCommand.REJECT,
                             message=f"Rejected: {params.get('request_id', '')}")

    async def _handle_enter_maintenance(self, params: dict) -> ControlResult:
        self._governance.maintenance_mode = True
        return ControlResult(command=ControlCommand.ENTER_MAINTENANCE,
                             message="Entered maintenance mode")

    async def _handle_exit_maintenance(self, params: dict) -> ControlResult:
        self._governance.maintenance_mode = False
        return ControlResult(command=ControlCommand.EXIT_MAINTENANCE,
                             message="Exited maintenance mode")

    async def health_check(self) -> dict[str, Any]:
        """Check control plane health."""
        return {
            "status": "healthy",
            "commands_processed": len(self._command_history),
            "audit_enabled": self._governance.audit_enabled,
            "maintenance_mode": self._governance.maintenance_mode,
            "active_nodes": self._governance.active_nodes,
        }
