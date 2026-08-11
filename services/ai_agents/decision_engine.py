"""
ICYQuant Decision Engine — final decision-making after consensus.

Aggregates all inputs (consensus, risk assessment, policy compliance,
guardrail checks) into a final actionable trading/research decision with
mandatory human-in-the-loop for high-stakes actions.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DecisionAction(str, Enum):
    APPROVE = "APPROVE"
    APPROVE_WITH_CONDITIONS = "APPROVE_WITH_CONDITIONS"
    HOLD = "HOLD"
    REJECT = "REJECT"
    ESCALATE = "ESCALATE"      # Requires human intervention
    NEEDS_MORE_DATA = "NEEDS_MORE_DATA"
    ABORT = "ABORT"            # Stop immediately


class DecisionDomain(str, Enum):
    STRATEGY = "strategy"
    TRADE = "trade"
    PORTFOLIO = "portfolio"
    RISK = "risk"
    RESEARCH = "research"
    CONFIGURATION = "configuration"


@dataclass
class DecisionContext:
    """All inputs considered for the decision."""
    consensus: Optional[Any] = None
    risk_assessment: Optional[Any] = None
    guardrail_checks: list[dict[str, Any]] = field(default_factory=list)
    policy_compliance: dict[str, bool] = field(default_factory=dict)
    backtest_results: Optional[Any] = None
    market_conditions: dict[str, Any] = field(default_factory=dict)


@dataclass
class Decision:
    """A final decision with full audit trail."""
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    domain: DecisionDomain = DecisionDomain.STRATEGY
    action: DecisionAction = DecisionAction.HOLD
    summary: str = ""

    # Scoring
    confidence: float = 0.0
    risk_score: float = 0.0
    urgency: str = "normal"     # low, normal, high, critical

    # Context
    context: DecisionContext = field(default_factory=DecisionContext)

    # Conditions and constraints
    conditions: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    expiration_seconds: int = 0  # 0 = no expiry

    # Audit trail
    reasoning: str = ""
    evidence: list[str] = field(default_factory=list)
    alternatives_considered: list[str] = field(default_factory=list)

    # Human-in-the-loop
    requires_approval: bool = False
    approved_by: str = ""
    approved_at: Optional[datetime] = None

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class DecisionEngine:
    """Final decision engine for the multi-agent system.

    Responsibilities:
        - Aggregate consensus, risk, policy, and guardrail inputs
        - Apply decision rules to determine action
        - Flag decisions requiring human approval
        - Generate decisions with full audit trail
        - Enforce mandatory human-in-the-loop for trading actions
    """

    # Actions that always require human approval
    HUMAN_REQUIRED_ACTIONS = {
        DecisionAction.APPROVE: {DecisionDomain.TRADE, DecisionDomain.PORTFOLIO},
        DecisionAction.APPROVE_WITH_CONDITIONS: {DecisionDomain.TRADE},
    }

    def __init__(self) -> None:
        self._decisions: dict[str, Decision] = {}
        self._total_decisions = 0

    async def decide(self,
                     domain: DecisionDomain,
                     context: DecisionContext,
                     confidence: float = 0.0,
                     risk_score: float = 0.0,
                     metadata: Optional[dict[str, Any]] = None) -> Decision:
        """Generate a decision from the provided context."""
        decision = Decision(
            domain=domain,
            context=context,
            confidence=confidence,
            risk_score=risk_score,
            metadata=metadata or {},
        )
        self._decisions[decision.decision_id] = decision
        self._total_decisions += 1

        # Step 1: Evaluate guardrail results
        guardrail_pass = self._evaluate_guardrails(context)

        # Step 2: Determine action
        decision.action = self._determine_action(domain, context, confidence,
                                                  risk_score, guardrail_pass)

        # Step 3: Check if human approval is required
        decision.requires_approval = self._check_human_required(decision)

        # Step 4: Generate reasoning
        decision.reasoning = self._build_reasoning(decision)

        # Step 5: Generate conditions/constraints
        if decision.action in (DecisionAction.APPROVE_WITH_CONDITIONS,):
            decision.conditions = self._generate_conditions(context)

        logger.info("Decision %s: %s [%s] confidence=%.2f human=%s",
                     decision.decision_id, decision.action.value,
                     domain.value, confidence, decision.requires_approval)

        return decision

    def approve(self, decision_id: str, approved_by: str) -> bool:
        """Record human approval of a decision."""
        decision = self._decisions.get(decision_id)
        if decision is None:
            return False
        if not decision.requires_approval:
            return False

        decision.approved_by = approved_by
        decision.approved_at = datetime.now(timezone.utc)
        decision.requires_approval = False
        logger.info("Decision %s approved by %s", decision_id, approved_by)
        return True

    def _evaluate_guardrails(self, context: DecisionContext) -> bool:
        """Check if all guardrails passed."""
        if not context.guardrail_checks:
            return True
        return all(check.get("passed", True) for check in context.guardrail_checks)

    def _determine_action(self, domain: DecisionDomain, context: DecisionContext,
                          confidence: float, risk_score: float,
                          guardrail_pass: bool) -> DecisionAction:
        """Apply decision logic to determine the action."""
        # Guardrail failure → abort
        if not guardrail_pass:
            return DecisionAction.ABORT

        # Risk too high → reject or escalate
        if risk_score > 0.8:
            return DecisionAction.REJECT
        if risk_score > 0.6:
            return DecisionAction.ESCALATE

        # Check consensus
        if context.consensus:
            consensus_level = getattr(context.consensus, 'level', None)
            if consensus_level:
                level_str = str(consensus_level)
                if "full" in level_str or "strong" in level_str:
                    if risk_score < 0.3:
                        return DecisionAction.APPROVE
                    return DecisionAction.APPROVE_WITH_CONDITIONS
                elif "moderate" in level_str:
                    return DecisionAction.APPROVE_WITH_CONDITIONS
                elif "weak" in level_str:
                    return DecisionAction.NEEDS_MORE_DATA
                elif "divided" in level_str:
                    return DecisionAction.ESCALATE

        # Policy compliance check
        if context.policy_compliance:
            if not all(context.policy_compliance.values()):
                return DecisionAction.REJECT

        # Low confidence → hold
        if confidence < 0.5:
            return DecisionAction.HOLD

        return DecisionAction.APPROVE_WITH_CONDITIONS

    def _check_human_required(self, decision: Decision) -> bool:
        """Check if the decision requires human sign-off."""
        if decision.action == DecisionAction.ESCALATE:
            return True
        if decision.action == DecisionAction.ABORT:
            return False  # Abort doesn't need approval; it stops action

        required = self.HUMAN_REQUIRED_ACTIONS.get(decision.action, set())
        return decision.domain in required

    def _build_reasoning(self, decision: Decision) -> str:
        """Build a human-readable reasoning string."""
        parts = [f"Decision: {decision.action.value}"]
        parts.append(f"Domain: {decision.domain.value}")

        if decision.confidence > 0:
            parts.append(f"Confidence: {decision.confidence:.1%}")
        if decision.risk_score > 0:
            parts.append(f"Risk: {decision.risk_score:.1%}")

        if decision.requires_approval:
            parts.append("[Requires human approval]")

        if decision.conditions:
            parts.append(f"Conditions: {'; '.join(decision.conditions[:3])}")

        return " | ".join(parts)

    def _generate_conditions(self, context: DecisionContext) -> list[str]:
        """Generate conditions for conditional approval."""
        conditions = []
        if context.risk_assessment:
            conditions.append("Validate risk limits before execution")
        if context.constraints:
            conditions.extend(context.constraints)
        return conditions or ["Monitor for adverse conditions"]

    def get_decision(self, decision_id: str) -> Optional[Decision]:
        return self._decisions.get(decision_id)

    def get_pending_approvals(self) -> list[Decision]:
        return [d for d in self._decisions.values() if d.requires_approval]

    @property
    def total_decisions(self) -> int:
        return self._total_decisions
