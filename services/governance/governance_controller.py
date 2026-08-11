"""
Governance Controller — bridges governance decisions into action signals.

This component translates governance verdicts into actionable instructions
for downstream systems (allocation, execution, risk).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from .governance_engine import GovernanceEngine, GovernanceVerdict
from .decision_context import DecisionContext
from .decision_request import DecisionRequest


class GovernanceAction(Enum):
    """Actions the governance controller can emit downstream."""

    ALLOW = auto()           # Proceed normally
    ALLOW_WITH_WARNING = auto()  # Proceed but log
    REDUCE_SCOPE = auto()    # Reduce requested amount
    REQUIRE_REVIEW = auto()  # Escalate for review
    FREEZE_NEW = auto()      # Freeze new decisions
    REDUCE = auto()          # Reduce exposure
    HEDGE = auto()           # Increase hedge
    EXIT = auto()            # Emergency exit
    REJECT = auto()          # Full reject


@dataclass
class GovernanceInstruction:
    """Downstream instruction from governance."""

    request_id: str
    action: GovernanceAction
    reason: str
    allowed_amount: Optional[float] = None
    max_allowed_risk: Optional[float] = None
    review_required: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GovernanceControllerConfig:
    """Configuration for the controller."""

    # Action mappings
    verdict_actions: Dict[str, GovernanceAction] = field(default_factory=lambda: {
        "ALLOW": GovernanceAction.ALLOW,
        "REVIEW": GovernanceAction.REQUIRE_REVIEW,
        "REJECT": GovernanceAction.REJECT,
        "BLOCKED": GovernanceAction.REJECT,
        "OVERRIDDEN": GovernanceAction.ALLOW,
        "EXPIRED": GovernanceAction.REJECT,
        "CANCELLED": GovernanceAction.REJECT,
    })

    # Emergency mode: when True, block-actions become emergency exit
    emergency_mode: bool = False

    # When current survival score falls below this, enter emergency
    emergency_survival_threshold: float = 40.0


class GovernanceController:
    """
    Translates governance engine output into concrete instructions for
    downstream subsystems (Allocation, Execution, Risk).
    """

    def __init__(
        self,
        engine: Optional[GovernanceEngine] = None,
        config: Optional[GovernanceControllerConfig] = None,
    ):
        self._engine = engine or GovernanceEngine()
        self._config = config or GovernanceControllerConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_and_instruct(
        self, request: DecisionRequest, context: DecisionContext
    ) -> GovernanceInstruction:
        """Run governance evaluation and produce an actionable instruction."""
        evaluation = self._engine.evaluate(request, context)
        return self._evaluation_to_instruction(evaluation, request, context)

    def instruct(
        self, request: DecisionRequest, context: DecisionContext
    ) -> GovernanceInstruction:
        """Shorthand for evaluate_and_instruct."""
        return self.evaluate_and_instruct(request, context)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _evaluation_to_instruction(
        self,
        evaluation,
        request: DecisionRequest,
        context: DecisionContext,
    ) -> GovernanceInstruction:
        verdict_name = evaluation.verdict.name
        base_action = self._config.verdict_actions.get(
            verdict_name, GovernanceAction.REJECT
        )

        # Emergency mode override
        if self._config.emergency_mode:
            survival = context.survival_score or 100
            if survival < self._config.emergency_survival_threshold:
                base_action = GovernanceAction.EXIT

        reason = evaluation.reason or f"Governance verdict: {verdict_name}"

        instruction = GovernanceInstruction(
            request_id=request.request_id,
            action=base_action,
            reason=reason,
            review_required=(verdict_name == "REVIEW"),
            metadata={
                "decision_id": evaluation.decision_id,
                "verdict": verdict_name,
                "actor": request.actor,
                "decision_type": request.decision_type,
            },
        )

        # Compute allowed amount (if constrained)
        if base_action == GovernanceAction.ALLOW:
            # Allow the full requested amount unless constraints say otherwise
            instruction.allowed_amount = request.requested_amount
        elif base_action == GovernanceAction.REDUCE_SCOPE:
            # Reduce to what constraints allow
            instruction.allowed_amount = self._compute_allowed_amount(request, context)

        return instruction

    def _compute_allowed_amount(
        self, request: DecisionRequest, context: DecisionContext
    ) -> float:
        """Compute max allowed amount from constraints."""
        # Start from requested, reduce based on constraints
        allowed = request.requested_amount or 0.0

        # Risk budget constraint
        if context.risk_budget_available is not None:
            allowed = min(allowed, context.risk_budget_available)

        # Capacity constraint
        if context.strategy_capacity is not None:
            allowed = min(allowed, context.strategy_capacity)

        return max(0.0, allowed)

    def set_emergency_mode(self, enabled: bool) -> None:
        self._config.emergency_mode = enabled
