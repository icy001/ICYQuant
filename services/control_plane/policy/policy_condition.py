"""
PolicyCondition — declarative condition over a PolicyContext.

Supported operators:

    equals / not_equals / greater_than / less_than
    contains / in / all / any

Example:

    PolicyCondition("risk_health", ConditionOperator.EQUALS, "UNHEALTHY")
    PolicyCondition("position_integrity", ConditionOperator.EQUALS, "UNTRUSTED")

Composite conditions combine children with AND / OR / NOT:

    (
        risk_health == UNHEALTHY
        OR position_integrity == UNTRUSTED
    )
    AND trading_state == TRADING_READY

Evaluation is a pure function of the context → deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Sequence, Tuple, Union


class ConditionOperator(str, Enum):
    """Comparison operators supported by a single PolicyCondition."""

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    CONTAINS = "contains"
    IN = "in"
    ALL = "all"
    ANY = "any"


class ConditionConnective(str, Enum):
    """Connectors for composite conditions."""

    AND = "and"
    OR = "or"
    NOT = "not"


def _value(v: Any) -> Any:
    """Normalise enum values so 'UNHEALTHY' == ComponentState.UNHEALTHY."""
    if isinstance(v, Enum):
        return v.value
    if isinstance(v, tuple):
        return tuple(_value(x) for x in v)
    if isinstance(v, list):
        return [_value(x) for x in v]
    if isinstance(v, dict):
        return {k: _value(x) for k, x in v.items()}
    return v


@dataclass(frozen=True)
class PolicyCondition:
    """A single comparison against a path in the PolicyContext."""

    field: str
    operator: ConditionOperator
    value: Any

    def evaluate(self, context: Any) -> bool:
        """Evaluate this condition against a context object."""
        actual = _value(context.resolve(self.field))
        expected = _value(self.value)
        op = self.operator

        if op is ConditionOperator.EQUALS:
            return actual == expected
        if op is ConditionOperator.NOT_EQUALS:
            return actual != expected
        if op is ConditionOperator.GREATER_THAN:
            return _compare(actual, expected, lambda a, b: a > b, "greater_than")
        if op is ConditionOperator.LESS_THAN:
            return _compare(actual, expected, lambda a, b: a < b, "less_than")
        if op is ConditionOperator.CONTAINS:
            if isinstance(actual, (str, bytes)):
                return expected in actual
            try:
                return expected in actual  # type: ignore[operator]
            except TypeError:
                return False
        if op is ConditionOperator.IN:
            return actual in expected  # type: ignore[operator]
        if op is ConditionOperator.ALL:
            return all(x in actual for x in expected)
        if op is ConditionOperator.ANY:
            return any(x in actual for x in expected)
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": "condition",
            "field": self.field,
            "operator": self.operator.value,
            "value": _value(self.value),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyCondition":
        return cls(
            field=data["field"],
            operator=ConditionOperator(data["operator"]),
            value=data["value"],
        )


def _compare(actual: Any, expected: Any, op: Any, name: str) -> bool:
    try:
        return op(actual, expected)
    except TypeError:
        return False


@dataclass(frozen=True)
class CompositeCondition:
    """A tree of conditions joined by AND / OR / NOT."""

    connective: ConditionConnective
    children: Tuple[Union["PolicyCondition", "CompositeCondition"], ...] = field(
        default_factory=tuple
    )

    def evaluate(self, context: Any) -> bool:
        results = [c.evaluate(context) for c in self.children]
        if self.connective is ConditionConnective.AND:
            return all(results)
        if self.connective is ConditionConnective.OR:
            return any(results)
        if self.connective is ConditionConnective.NOT:
            return not results[0]
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": "composite",
            "connective": self.connective.value,
            "children": [c.to_dict() for c in self.children],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CompositeCondition":
        children = tuple(_condition_from_dict(c) for c in data["children"])
        return cls(connective=ConditionConnective(data["connective"]), children=children)


def _condition_from_dict(
    data: Dict[str, Any],
) -> Union[PolicyCondition, CompositeCondition]:
    if data.get("kind") == "composite":
        return CompositeCondition.from_dict(data)
    return PolicyCondition.from_dict(data)


# ----------------------------------------------------------------------
# factories
# ----------------------------------------------------------------------


def condition(path: str, op: str, value: Any) -> PolicyCondition:
    """Shortcut: ``condition("risk_health", "equals", "UNHEALTHY")``."""
    return PolicyCondition(field=path, operator=ConditionOperator(op), value=value)


def and_(*children: Union[PolicyCondition, CompositeCondition]) -> CompositeCondition:
    return CompositeCondition(ConditionConnective.AND, children)


def or_(*children: Union[PolicyCondition, CompositeCondition]) -> CompositeCondition:
    return CompositeCondition(ConditionConnective.OR, children)


def not_(*children: Union[PolicyCondition, CompositeCondition]) -> CompositeCondition:
    return CompositeCondition(ConditionConnective.NOT, children)


def evaluate_condition(
    condition: Union[PolicyCondition, CompositeCondition], context: Any
) -> bool:
    """Evaluate either a leaf or a composite condition."""
    return condition.evaluate(context)
