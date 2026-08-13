"""Commit 28 Part 1.2 — Policy Conditions.

Typed, declarative conditions used by the deterministic policy
evaluation engine. No dynamic code execution: a condition is always
``field <operator> value`` evaluated against a GovernanceContext.
"""

from dataclasses import dataclass
from enum import Enum


class ConditionOperator(str, Enum):
    """Supported condition operators."""

    EQUALS = "EQUALS"
    NOT_EQUALS = "NOT_EQUALS"
    IN = "IN"
    NOT_IN = "NOT_IN"
    EXISTS = "EXISTS"


@dataclass(frozen=True)
class PolicyCondition:
    """A single typed condition: ``context.field <operator> value``."""

    field: str
    operator: ConditionOperator
    value: object


class ConditionEvaluator:
    """Evaluates a PolicyCondition against a GovernanceContext.

    The field is resolved with ``getattr`` on the context; a missing
    attribute evaluates to ``None`` (so EXISTS fails, EQUALS to None
    only succeeds when the value is also None).
    """

    def evaluate(self, condition: PolicyCondition, context: object) -> bool:
        actual = getattr(context, condition.field, None)

        if condition.operator == ConditionOperator.EQUALS:
            return actual == condition.value

        if condition.operator == ConditionOperator.NOT_EQUALS:
            return actual != condition.value

        if condition.operator == ConditionOperator.IN:
            return actual in condition.value

        if condition.operator == ConditionOperator.NOT_IN:
            return actual not in condition.value

        if condition.operator == ConditionOperator.EXISTS:
            return actual is not None

        return False
