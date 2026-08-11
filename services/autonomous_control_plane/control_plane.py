"""
Autonomous Quant Control Plane — Central Governance Platform

The ControlPlane is the top-level governance orchestrator for the entire
ICYQuant autonomous quant system. It provides unified policy enforcement,
decision lifecycle management, autonomy level control, and cross-domain
coordination.

Architecture:
    Policy Engine → Autonomy Engine → Decision Engine → Audit Engine
    Budget Manager → Model Lifecycle → Promotion Engine → Approval Engine
    Permission Engine → Incident Manager → Health Monitor → Safety Layer
"""

from __future__ import annotations

import uuid
import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ControlPlaneMode(Enum):
    """Overall operational mode of the Control Plane."""
    INITIALIZING = "initializing"
    ACTIVE = "active"
    DEGRADED = "degraded"
    RESTRICTED = "restricted"
    HALTED = "halted"
    RECOVERING = "recovering"


class ControlPlaneDecision(Enum):
    """Top-level decisions from the Control Plane."""
    ALLOW = "allow"
    DENY = "deny"
    RESIZE = "resize"
    DEFER = "defer"
    REVIEW = "review"
    QUARANTINE = "quarantine"
    ROLLBACK = "rollback"
    HALT = "halt"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ControlPlaneContext:
    """Global context passed through the Control Plane decision pipeline."""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)

    # Domain contexts (populated by respective engines)
    market_context: Optional[dict] = None
    research_context: Optional[dict] = None
    alpha_context: Optional[dict] = None
    strategy_context: Optional[dict] = None
    portfolio_context: Optional[dict] = None
    risk_context: Optional[dict] = None
    execution_context: Optional[dict] = None

    # Control contexts
    policy_context: Optional[dict] = None
    permission_context: Optional[dict] = None
    autonomy_context: Optional[dict] = None
    budget_context: Optional[dict] = None
    system_health_context: Optional[dict] = None

    def snapshot(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "market_context": self.market_context,
            "research_context": self.research_context,
            "alpha_context": self.alpha_context,
            "strategy_context": self.strategy_context,
            "portfolio_context": self.portfolio_context,
            "risk_context": self.risk_context,
            "execution_context": self.execution_context,
            "policy_context": self.policy_context,
            "permission_context": self.permission_context,
            "autonomy_context": self.autonomy_context,
            "budget_context": self.budget_context,
            "system_health_context": self.system_health_context,
        }


# ---------------------------------------------------------------------------
# ControlPlane
# ---------------------------------------------------------------------------

class ControlPlane:
    """
    Central governance platform for the autonomous quant system.

    The ControlPlane sits above all domain engines (Research, Alpha, Strategy,
    Portfolio, Risk, Execution) and provides cross-cutting governance:
    policy enforcement, budget constraints, autonomy level control,
    model lifecycle management, approval gates, and audit trails.

    It is NOT another trading engine — it is the governance layer that
    determines whether, how, and with what authority the trading engines
    may operate.
    """

    def __init__(
        self,
        policy_engine=None,
        autonomy_engine=None,
        decision_engine=None,
        budget_manager=None,
        lifecycle_engine=None,
        promotion_engine=None,
        approval_engine=None,
        permission_engine=None,
        audit_engine=None,
        incident_manager=None,
        health_monitor=None,
        safety_layer=None,
    ):
        self._policy_engine = policy_engine
        self._autonomy_engine = autonomy_engine
        self._decision_engine = decision_engine
        self._budget_manager = budget_manager
        self._lifecycle_engine = lifecycle_engine
        self._promotion_engine = promotion_engine
        self._approval_engine = approval_engine
        self._permission_engine = permission_engine
        self._audit_engine = audit_engine
        self._incident_manager = incident_manager
        self._health_monitor = health_monitor
        self._safety_layer = safety_layer

        self._mode = ControlPlaneMode.INITIALIZING
        self._started_at = time.time()
        self._decision_count = 0
        self._denial_count = 0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def mode(self) -> ControlPlaneMode:
        return self._mode

    @property
    def is_active(self) -> bool:
        return self._mode == ControlPlaneMode.ACTIVE

    @property
    def is_halted(self) -> bool:
        return self._mode == ControlPlaneMode.HALTED

    @property
    def policy_engine(self):
        return self._policy_engine

    @property
    def autonomy_engine(self):
        return self._autonomy_engine

    @property
    def decision_engine(self):
        return self._decision_engine

    @property
    def budget_manager(self):
        return self._budget_manager

    @property
    def lifecycle_engine(self):
        return self._lifecycle_engine

    @property
    def promotion_engine(self):
        return self._promotion_engine

    @property
    def approval_engine(self):
        return self._approval_engine

    @property
    def permission_engine(self):
        return self._permission_engine

    @property
    def audit_engine(self):
        return self._audit_engine

    @property
    def incident_manager(self):
        return self._incident_manager

    @property
    def health_monitor(self):
        return self._health_monitor

    @property
    def safety_layer(self):
        return self._safety_layer

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the Control Plane and transition to ACTIVE mode."""
        logger.info("ControlPlane starting...")
        self._mode = ControlPlaneMode.INITIALIZING

        # Initialize sub-engines
        if self._policy_engine:
            await self._policy_engine.start()
        if self._autonomy_engine:
            await self._autonomy_engine.start()
        if self._decision_engine:
            await self._decision_engine.start()
        if self._lifecycle_engine:
            await self._lifecycle_engine.start()
        if self._health_monitor:
            await self._health_monitor.start()

        self._mode = ControlPlaneMode.ACTIVE
        logger.info("ControlPlane started — ACTIVE")

    async def stop(self) -> None:
        """Gracefully stop the Control Plane."""
        self._mode = ControlPlaneMode.HALTED
        logger.info("ControlPlane stopping...")
        if self._decision_engine:
            await self._decision_engine.stop()
        if self._health_monitor:
            await self._health_monitor.stop()

    # ------------------------------------------------------------------
    # Decision Pipeline
    # ------------------------------------------------------------------

    async def evaluate(self, context: ControlPlaneContext) -> ControlPlaneDecision:
        """
        Central decision pipeline — evaluates a request through all
        governance layers and returns the effective decision.

        Pipeline order:
            Health → Safety → Policy → Budget → Autonomy → Permission
            → Lifecycle → Approval → Final Decision
        """
        if self._mode != ControlPlaneMode.ACTIVE:
            logger.warning("ControlPlane not ACTIVE — DENY all decisions")
            return ControlPlaneDecision.DENY

        self._decision_count += 1

        # 1. Health check
        if self._health_monitor:
            health = await self._health_monitor.check()
            context.system_health_context = health
            if health.get("overall") == "CRITICAL":
                self._denial_count += 1
                return ControlPlaneDecision.HALT

        # 2. Safety layer (circuit breaker / kill switch)
        if self._safety_layer:
            safety = await self._safety_layer.check(context)
            if not safety.allowed:
                self._denial_count += 1
                return safety.decision

        # 3. Policy engine
        if self._policy_engine:
            policy_result = await self._policy_engine.evaluate(context)
            if policy_result.decision != ControlPlaneDecision.ALLOW:
                self._denial_count += 1
                return policy_result.decision

        # 4. Budget
        if self._budget_manager:
            budget = await self._budget_manager.check(context)
            if not budget.allowed:
                self._denial_count += 1
                return ControlPlaneDecision.DENY

        # 5. Autonomy
        if self._autonomy_engine:
            autonomy = await self._autonomy_engine.evaluate(context)
            if not autonomy.allowed:
                self._denial_count += 1
                return autonomy.decision

        # 6. Permission
        if self._permission_engine:
            perm = await self._permission_engine.check(context)
            if not perm.allowed:
                self._denial_count += 1
                return ControlPlaneDecision.DENY

        # 7. Lifecycle
        if self._lifecycle_engine:
            lifecycle = await self._lifecycle_engine.evaluate(context)
            if not lifecycle.allowed:
                self._denial_count += 1
                return lifecycle.decision

        # 8. Approval
        if self._approval_engine:
            approval = await self._approval_engine.evaluate(context)
            if not approval.allowed:
                self._denial_count += 1
                return approval.decision

        # 9. Decision engine — record & finalize
        if self._decision_engine:
            final = await self._decision_engine.decide(context)
            return final

        return ControlPlaneDecision.ALLOW

    # ------------------------------------------------------------------
    # Governance Operations
    # ------------------------------------------------------------------

    async def promote_model(self, model_id: str, target_state: str) -> bool:
        """Promote a model through the lifecycle stages."""
        if self._promotion_engine:
            return await self._promotion_engine.promote(model_id, target_state)
        return False

    async def demote_model(self, model_id: str, reason: str) -> bool:
        """Demote a model due to degradation."""
        if self._promotion_engine:
            return await self._promotion_engine.demote(model_id, reason)
        return False

    async def rollback_model(self, model_id: str, target_version: str) -> bool:
        """Rollback a model to a previous version."""
        if self._promotion_engine:
            return await self._promotion_engine.rollback(model_id, target_version)
        return False

    async def quarantine_model(self, model_id: str, reason: str) -> bool:
        """Quarantine a degraded or anomalous model."""
        if self._promotion_engine:
            return await self._promotion_engine.quarantine(model_id, reason)
        return False

    async def trigger_kill_switch(self, reason: str) -> None:
        """Activate the global kill switch."""
        self._mode = ControlPlaneMode.HALTED
        logger.critical("GLOBAL KILL SWITCH ACTIVATED: %s", reason)
        if self._safety_layer:
            await self._safety_layer.activate_kill_switch(reason)
        if self._incident_manager:
            await self._incident_manager.create_incident("kill_switch", reason)

    async def human_override(self, decision_id: str, action: str, operator: str, reason: str) -> bool:
        """Apply a human override to a pending or active decision."""
        if self._approval_engine:
            return await self._approval_engine.override(decision_id, action, operator, reason)
        return False

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        return {
            "mode": self._mode.value,
            "uptime_seconds": time.time() - self._started_at,
            "decisions_total": self._decision_count,
            "denials_total": self._denial_count,
            "denial_rate": self._denial_count / max(self._decision_count, 1),
        }
