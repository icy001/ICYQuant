"""Commit 28 Part 1.2 — Policy Evaluator.

Deterministically matches a single Policy against a GovernanceContext:

    enabled + resource + action + required_roles + ALL conditions

No dynamic code execution; every predicate is explicit and testable.
"""

from __future__ import annotations

from .condition import ConditionEvaluator


class PolicyEvaluator:
    """Matches a Policy against a GovernanceContext.

    A policy matches only when:

      - it is enabled
      - resource and action equal the request
      - the request holds at least one of the required roles (if any)
      - every condition evaluates to True (AND semantics)
    """

    def __init__(
        self,
        condition_evaluator: ConditionEvaluator | None = None,
    ) -> None:
        self._condition_evaluator = condition_evaluator or ConditionEvaluator()

    def matches(self, policy, context: object) -> bool:
        if not policy.enabled:
            return False

        if policy.resource != context.resource:
            return False

        if policy.action != context.action:
            return False

        if policy.required_roles and not any(
            role in context.role_ids for role in policy.required_roles
        ):
            return False

        return all(
            self._condition_evaluator.evaluate(condition, context)
            for condition in policy.conditions
        )
