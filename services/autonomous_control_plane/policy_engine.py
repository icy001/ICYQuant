"""
Policy Engine — Central policy evaluation and enforcement.

Evaluates all autonomous decisions against the active policy set,
resolves policy conflicts, and returns policy-based decisions.
"""

from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PolicyEvaluationOutcome(Enum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    CONFLICT = "conflict"
    OVERRIDDEN = "overridden"


class PolicyEngine:
    """
    Central policy enforcement engine.

    Maintains active policies across all domains (Research, Alpha,
    Strategy, Portfolio, Risk, Execution, Capital, Production),
    evaluates decisions against them, and resolves conflicts with
    conservative precedence rules.
    """

    def __init__(self, registry=None, conflict_resolver=None):
        from .policy_registry import PolicyRegistry
        from .policy_conflict_resolver import PolicyConflictResolver
        self._registry = registry or PolicyRegistry()
        self._conflict_resolver = conflict_resolver or PolicyConflictResolver()
        self._evaluation_count = 0
        self._violation_count = 0
        self._conflict_count = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self):
        logger.info("PolicyEngine started")

    # ------------------------------------------------------------------
    # Policy Management
    # ------------------------------------------------------------------

    def register_policy(self, policy) -> None:
        """Register a new policy."""
        self._registry.add(policy)

    def get_active_policies(self, scope: str = None) -> list:
        """Get all currently active policies, optionally filtered by scope."""
        return self._registry.active(scope)

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    async def evaluate(self, context) -> object:
        """
        Evaluate a context against all applicable policies.

        Returns a result with .decision property indicating ALLOW or
        the restrictive decision (DENY, RESIZE, etc.).
        """
        from .control_plane import ControlPlaneDecision
        from .decision_result import DecisionResult, DecisionOutcome

        self._evaluation_count += 1

        scope = getattr(context, "requested_scope", "default")
        policies = self.get_active_policies(scope)

        if not policies:
            return DecisionResult.allowed_result()

        # Evaluate each policy
        evaluations = []
        for policy in policies:
            try:
                result = policy.evaluate(context)
                evaluations.append(result)
            except Exception:
                logger.exception("Policy evaluation error: %s", getattr(policy, "policy_id", "?"))
                continue

        # Check for conflicts
        conflict_result = self._conflict_resolver.resolve(evaluations)
        if conflict_result.has_conflict:
            self._conflict_count += 1
            logger.warning("Policy conflict detected in scope=%s", scope)

        # Most restrictive wins
        restrictiveness = {
            ControlPlaneDecision.ALLOW: 0,
            ControlPlaneDecision.RESIZE: 1,
            ControlPlaneDecision.DEFER: 2,
            ControlPlaneDecision.REVIEW: 3,
            ControlPlaneDecision.QUARANTINE: 4,
            ControlPlaneDecision.ROLLBACK: 5,
            ControlPlaneDecision.DENY: 6,
            ControlPlaneDecision.HALT: 7,
        }

        most_restrictive = ControlPlaneDecision.ALLOW
        for eval_result in evaluations:
            decision = getattr(eval_result, "decision", ControlPlaneDecision.ALLOW)
            if restrictiveness.get(decision, 0) > restrictiveness.get(most_restrictive, 0):
                most_restrictive = decision

        if most_restrictive != ControlPlaneDecision.ALLOW:
            self._violation_count += 1

        outcome_map = {
            ControlPlaneDecision.ALLOW: DecisionOutcome.ALLOW,
            ControlPlaneDecision.DENY: DecisionOutcome.DENY,
            ControlPlaneDecision.RESIZE: DecisionOutcome.RESIZE,
            ControlPlaneDecision.DEFER: DecisionOutcome.DEFER,
            ControlPlaneDecision.REVIEW: DecisionOutcome.REVIEW,
            ControlPlaneDecision.QUARANTINE: DecisionOutcome.QUARANTINE,
            ControlPlaneDecision.ROLLBACK: DecisionOutcome.ROLLBACK,
            ControlPlaneDecision.HALT: DecisionOutcome.HALT,
        }

        return DecisionResult(
            outcome=outcome_map.get(most_restrictive, DecisionOutcome.DENY),
            allowed=most_restrictive == ControlPlaneDecision.ALLOW,
            reason=f"policy_evaluation: {most_restrictive.value}" if most_restrictive != ControlPlaneDecision.ALLOW else None,
        )

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        return {
            "evaluations_total": self._evaluation_count,
            "violations_total": self._violation_count,
            "conflicts_total": self._conflict_count,
            "active_policies": len(self.get_active_policies()),
        }
