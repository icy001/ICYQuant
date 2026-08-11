"""
Pre-Trade Risk Manager — Orchestrates the pre-trade risk platform.

Wires together the engine, rule chain, approval workflow, runtime,
and observability components into a cohesive management layer.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from .pre_trade_engine import PreTradeRiskEngine
from .pre_trade_runtime import PreTradeRuntime, RuntimeConfig
from .risk_rule_chain import RiskRuleChain
from .approval_workflow import ApprovalWorkflow
from .approval_policy import ApprovalPolicy
from .risk_request import RiskRequest
from .risk_decision import RiskDecision

logger = logging.getLogger(__name__)


class PreTradeManager:
    """
    Top-level orchestrator for the Pre-Trade Risk Platform.

    Manages the lifecycle of all components: engine, runtime, rule chain,
    approval workflow, and observability services.

    Usage::

        manager = PreTradeManager()
        await manager.initialize()
        await manager.start()

        decision = await manager.evaluate(request)
        if decision.is_approved:
            # forward to OMS
            ...
    """

    def __init__(
        self,
        engine: Optional[PreTradeRiskEngine] = None,
        runtime: Optional[PreTradeRuntime] = None,
        rule_chain: Optional[RiskRuleChain] = None,
        approval_workflow: Optional[ApprovalWorkflow] = None,
        approval_policy: Optional[ApprovalPolicy] = None,
    ) -> None:
        self._rule_chain = rule_chain or RiskRuleChain()
        self._approval_workflow = approval_workflow or ApprovalWorkflow()
        self._approval_policy = approval_policy or ApprovalPolicy()
        self._runtime = runtime or PreTradeRuntime(config=RuntimeConfig())
        self._engine = engine or PreTradeRiskEngine(
            rule_chain=self._rule_chain,
            approval_workflow=self._approval_workflow,
            approval_policy=self._approval_policy,
        )
        self._initialized = False

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize all pre-trade components."""
        logger.info("PreTradeManager initializing...")
        await self._runtime.initialize()
        await self._engine.initialize()
        self._initialized = True
        logger.info("PreTradeManager initialized.")

    async def start(self) -> None:
        """Start the pre-trade platform."""
        if not self._initialized:
            await self.initialize()
        await self._runtime.start()
        logger.info("PreTradeManager started.")

    async def stop(self) -> None:
        """Stop the pre-trade platform gracefully."""
        logger.info("PreTradeManager stopping...")
        await self._runtime.stop()
        self._initialized = False
        logger.info("PreTradeManager stopped.")

    # ---- Core API ----

    async def evaluate(self, request: RiskRequest) -> RiskDecision:
        """
        Evaluate an order intent through the full pre-trade pipeline.

        Acquires a runtime slot, runs the evaluation, and releases.
        """
        if self._runtime.status.value != "running":
            logger.warning("Runtime not running; starting automatically.")
            await self.start()

        acquired = await self._runtime.acquire()
        if not acquired:
            logger.error(f"Failed to acquire runtime slot for {request.request_id}")
            return RiskDecision.rejected(
                request_id=request.request_id,
                risk_score=100.0,
                triggered_rules=["runtime_capacity"],
                reasons=[{"message": "Runtime capacity exceeded; unable to evaluate."}],
            )

        try:
            decision = await self._engine.evaluate(request)
            if decision.is_rejected:
                await self._runtime.record_rejection()
            await self._runtime.release(success=True)
            return decision
        except Exception as e:
            logger.error(f"Evaluation failed for {request.request_id}: {e}")
            await self._runtime.release(success=False)
            return RiskDecision.rejected(
                request_id=request.request_id,
                risk_score=100.0,
                triggered_rules=["engine_failure"],
                reasons=[{"message": f"Engine failure: {str(e)}"}],
            )

    async def validate(self, request: RiskRequest) -> bool:
        """Quick validation — returns True if request passes."""
        decision = await self.evaluate(request)
        return decision.is_approved

    async def approve(self, decision_id: str, approver: str) -> Optional[RiskDecision]:
        """Manually approve a pending decision."""
        return await self._approval_workflow.approve(decision_id, approver)

    async def reject(
        self, decision_id: str, approver: str, reason: str = ""
    ) -> Optional[RiskDecision]:
        """Manually reject a pending decision."""
        return await self._approval_workflow.reject(decision_id, approver, reason)

    # ---- Component Access ----

    @property
    def engine(self) -> PreTradeRiskEngine:
        return self._engine

    @property
    def runtime(self) -> PreTradeRuntime:
        return self._runtime

    @property
    def rule_chain(self) -> RiskRuleChain:
        return self._rule_chain

    @property
    def approval_workflow(self) -> ApprovalWorkflow:
        return self._approval_workflow

    # ---- Observability ----

    async def get_stats(self) -> dict[str, Any]:
        """Aggregate stats from all components."""
        engine_stats = await self._engine.get_stats() if self._engine else {}
        runtime_health = await self._runtime.health_check() if self._runtime else {}
        return {
            "engine": engine_stats,
            "runtime": runtime_health,
            "rule_chain": self._rule_chain.get_stats(),
        }

    async def health_check(self) -> dict[str, Any]:
        """Check health of all managed components."""
        return {
            "initialized": self._initialized,
            "runtime": await self._runtime.health_check(),
            "rule_chain": len(self._rule_chain.rules),
        }
