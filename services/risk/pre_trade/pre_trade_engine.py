"""
Pre-Trade Risk Engine — Unified entry point for all pre-trade risk evaluation.

Every order intent must pass through this engine before reaching OMS.
It orchestrates the rule chain, collects checker results, builds risk
decisions, and routes through the approval workflow.

Architecture::

    Order Intent → Rule Chain → Risk Decision → Approval → OMS
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

from .risk_request import RiskRequest
from .risk_decision import RiskDecision, Decision
from .pre_trade_context import PreTradeContext
from .risk_rule_chain import RiskRuleChain
from .approval_workflow import ApprovalWorkflow
from .approval_policy import ApprovalPolicy, ApprovalAction

logger = logging.getLogger(__name__)


class PreTradeRiskEngine:
    """
    Production pre-trade risk engine — the first line of defense.

    All order intents must be evaluated through this engine before
    being forwarded to OMS. The engine runs the rule chain, builds
    a risk decision, and routes through the approval workflow.

    Usage::

        engine = PreTradeRiskEngine(rule_chain=chain, approval=workflow)
        await engine.initialize()

        request = RiskRequest(account_id="ACC-01", symbol="AAPL", ...)
        decision = await engine.evaluate(request)
        if decision.is_approved:
            await oms.submit(order)
    """

    def __init__(
        self,
        rule_chain: Optional[RiskRuleChain] = None,
        approval_workflow: Optional[ApprovalWorkflow] = None,
        approval_policy: Optional[ApprovalPolicy] = None,
        engine_id: str = "PTRE-01",
    ) -> None:
        self.engine_id = engine_id
        self._rule_chain = rule_chain or RiskRuleChain()
        self._approval_workflow = approval_workflow or ApprovalWorkflow()
        self._approval_policy = approval_policy or ApprovalPolicy()
        self._initialized = False
        self._stats: dict[str, int] = {
            "total_requests": 0,
            "approved": 0,
            "rejected": 0,
            "escalated": 0,
            "manual_approval": 0,
        }
        self._lock = asyncio.Lock()

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize the engine and all checkers."""
        logger.info(f"PreTradeRiskEngine [{self.engine_id}] initializing...")
        await self._rule_chain.initialize()
        self._initialized = True
        logger.info(f"PreTradeRiskEngine [{self.engine_id}] initialized.")

    # ---- Core API ----

    async def evaluate(self, request: RiskRequest) -> RiskDecision:
        """
        Evaluate an order intent through the full risk pipeline.

        Pipeline: Request → Context → Rule Chain → Build Decision → Approval → Decision

        Returns a RiskDecision that OMS can use to approve/reject/escalate.
        """
        if not self._initialized:
            await self.initialize()

        t_start = time.perf_counter()
        async with self._lock:
            self._stats["total_requests"] += 1

        # Phase 1: Create evaluation context
        ctx = PreTradeContext(request=request)

        # Phase 2: Run rule chain
        ctx = await self._rule_chain.execute(ctx)

        # Phase 3: Build risk decision
        decision = ctx.build_decision()
        decision = RiskDecision(
            decision_id=decision.decision_id,
            request_id=decision.request_id,
            engine_id=self.engine_id,
            decision=decision.decision,
            risk_level=decision.risk_level,
            risk_score=decision.risk_score,
            triggered_rules=decision.triggered_rules,
            passed_rules=decision.passed_rules,
            reasons=decision.reasons,
            checker_results=decision.checker_results,
            requires_manual_approval=decision.requires_manual_approval,
            evaluation_time_ms=(time.perf_counter() - t_start) * 1000,
        )

        # Phase 4: Approval routing
        action = self._approval_policy.evaluate(
            risk_score=decision.risk_score,
            triggered_rules=decision.triggered_rules,
            risk_level=decision.risk_level.value,
        )

        decision = await self._apply_approval_action(decision, action)

        # Update stats
        async with self._lock:
            if decision.is_approved:
                self._stats["approved"] += 1
            elif decision.is_rejected:
                self._stats["rejected"] += 1
            elif decision.needs_escalation:
                self._stats["escalated"] += 1

        logger.info(
            f"Evaluation complete: {request.request_id} → {decision.decision.value} "
            f"(score={decision.risk_score:.1f}, time={decision.evaluation_time_ms:.1f}ms)"
        )
        return decision

    async def validate(self, request: RiskRequest) -> bool:
        """Quick validation pass — returns True if order passes all checks."""
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

    # ---- Stats ----

    async def get_stats(self) -> dict[str, Any]:
        """Get engine statistics."""
        async with self._lock:
            return dict(self._stats)

    # ---- Internal ----

    async def _apply_approval_action(
        self, decision: RiskDecision, action: ApprovalAction
    ) -> RiskDecision:
        """Apply approval routing action to the decision."""
        if action == ApprovalAction.AUTO_APPROVE:
            return RiskDecision(
                **{**decision.__dict__, "decision": Decision.APPROVED}
            )
        if action == ApprovalAction.AUTO_REJECT:
            return RiskDecision(
                **{**decision.__dict__, "decision": Decision.REJECTED}
            )
        if action in (ApprovalAction.ROUTE_TO_APPROVER, ApprovalAction.ROUTE_TO_ADMIN):
            return RiskDecision(
                **{
                    **decision.__dict__,
                    "decision": Decision.MANUAL_APPROVAL,
                    "requires_manual_approval": True,
                }
            )
        if action == ApprovalAction.ESCALATE:
            return RiskDecision(
                **{
                    **decision.__dict__,
                    "decision": Decision.ESCALATED,
                    "requires_manual_approval": True,
                }
            )
        return decision
