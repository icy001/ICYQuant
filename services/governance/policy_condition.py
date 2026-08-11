"""
Policy Condition — composable conditions for policy rules.

For tree-structured expression evaluation, see: policy_expression.py
which provides PolicyExpression with logical/arithmetic/aggregation/fomula types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional


class ConditionOperator(Enum):
    """Comparison operators for conditions."""

    EQUAL = auto()
    NOT_EQUAL = auto()
    GREATER_THAN = auto()
    GREATER_OR_EQUAL = auto()
    LESS_THAN = auto()
    LESS_OR_EQUAL = auto()
    IN_RANGE = auto()
    OUT_OF_RANGE = auto()
    EXISTS = auto()
    NOT_EXISTS = auto()


class ConditionLogic(Enum):
    """Logic combinators for multiple conditions."""

    AND = auto()
    OR = auto()
    NOT = auto()


@dataclass
class PolicyCondition:
    """A single evaluable condition within a policy rule."""

    condition_id: str = ""
    metric: str = ""
    operator: ConditionOperator = ConditionOperator.GREATER_THAN
    value: Any = None
    value_range: Optional[tuple] = None  # For IN_RANGE / OUT_OF_RANGE
    description: str = ""

    def evaluate(self, context_value: Any) -> bool:
        """Evaluate this condition against a context value."""
        try:
            if self.operator == ConditionOperator.EQUAL:
                return context_value == self.value
            elif self.operator == ConditionOperator.NOT_EQUAL:
                return context_value != self.value
            elif self.operator == ConditionOperator.GREATER_THAN:
                return float(context_value) > float(self.value)
            elif self.operator == ConditionOperator.GREATER_OR_EQUAL:
                return float(context_value) >= float(self.value)
            elif self.operator == ConditionOperator.LESS_THAN:
                return float(context_value) < float(self.value)
            elif self.operator == ConditionOperator.LESS_OR_EQUAL:
                return float(context_value) <= float(self.value)
            elif self.operator == ConditionOperator.IN_RANGE:
                if self.value_range:
                    lo, hi = self.value_range
                    return lo <= float(context_value) <= hi
                return False
            elif self.operator == ConditionOperator.OUT_OF_RANGE:
                if self.value_range:
                    lo, hi = self.value_range
                    return not (lo <= float(context_value) <= hi)
                return True
            elif self.operator == ConditionOperator.EXISTS:
                return context_value is not None
            elif self.operator == ConditionOperator.NOT_EXISTS:
                return context_value is None
            return False
        except (TypeError, ValueError):
            return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "condition_id": self.condition_id,
            "metric": self.metric,
            "operator": self.operator.name,
            "value": self.value,
            "value_range": self.value_range,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyCondition":
        return cls(
            condition_id=data.get("condition_id", ""),
            metric=data.get("metric", ""),
            operator=ConditionOperator[data.get("operator", "GREATER_THAN")],
            value=data.get("value"),
            value_range=tuple(data["value_range"]) if data.get("value_range") else None,
            description=data.get("description", ""),
        )
