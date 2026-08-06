"""
Condition — conditional expression evaluation for branch execution.

Supports:
- Boolean expressions
- Comparison operators
- Data-driven conditions
- Nested conditions (AND/OR/NOT)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class ConditionOperator(str, Enum):
    EQUALS = "eq"
    NOT_EQUALS = "ne"
    GREATER_THAN = "gt"
    GREATER_EQUAL = "ge"
    LESS_THAN = "lt"
    LESS_EQUAL = "le"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    MATCHES = "matches"  # regex
    CUSTOM = "custom"


class LogicalOperator(str, Enum):
    AND = "and"
    OR = "or"
    NOT = "not"


@dataclass
class Condition:
    """A single condition to evaluate."""

    field: str
    operator: ConditionOperator
    value: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate this condition against a context dictionary."""
        field_value = context.get(self.field)

        try:
            if self.operator == ConditionOperator.EQUALS:
                return field_value == self.value
            elif self.operator == ConditionOperator.NOT_EQUALS:
                return field_value != self.value
            elif self.operator == ConditionOperator.GREATER_THAN:
                return field_value is not None and field_value > self.value
            elif self.operator == ConditionOperator.GREATER_EQUAL:
                return field_value is not None and field_value >= self.value
            elif self.operator == ConditionOperator.LESS_THAN:
                return field_value is not None and field_value < self.value
            elif self.operator == ConditionOperator.LESS_EQUAL:
                return field_value is not None and field_value <= self.value
            elif self.operator == ConditionOperator.IN:
                return field_value in (self.value or [])
            elif self.operator == ConditionOperator.NOT_IN:
                return field_value not in (self.value or [])
            elif self.operator == ConditionOperator.CONTAINS:
                return self.value in (field_value or "")
            elif self.operator == ConditionOperator.STARTS_WITH:
                return str(field_value or "").startswith(str(self.value))
            elif self.operator == ConditionOperator.ENDS_WITH:
                return str(field_value or "").endswith(str(self.value))
            elif self.operator == ConditionOperator.IS_NULL:
                return field_value is None
            elif self.operator == ConditionOperator.IS_NOT_NULL:
                return field_value is not None
            elif self.operator == ConditionOperator.MATCHES:
                import re
                return bool(re.match(str(self.value), str(field_value or "")))
            elif self.operator == ConditionOperator.CUSTOM:
                if callable(self.value):
                    return self.value(field_value, context)
                return False
            else:
                return False
        except Exception:
            logger.exception(f"Error evaluating condition {self.field} {self.operator}")
            return False


@dataclass
class ConditionGroup:
    """A group of conditions combined with a logical operator."""

    conditions: List[Union[Condition, "ConditionGroup"]] = field(default_factory=list)
    operator: LogicalOperator = LogicalOperator.AND

    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate the condition group."""
        if not self.conditions:
            return True

        if self.operator == LogicalOperator.NOT:
            return not self.conditions[0].evaluate(context)

        results = [c.evaluate(context) for c in self.conditions]

        if self.operator == LogicalOperator.AND:
            return all(results)
        elif self.operator == LogicalOperator.OR:
            return any(results)
        return False


class ConditionEvaluator:
    """
    Evaluates conditions for branch execution.

    Usage:
        evaluator = ConditionEvaluator()
        condition = Condition(field="order.amount", operator=ConditionOperator.GT, value=10000)
        result = evaluator.evaluate(condition, {"order": {"amount": 15000}})  # True
    """

    def evaluate(
        self,
        condition: Union[Condition, ConditionGroup],
        context: Dict[str, Any],
    ) -> bool:
        """Evaluate a condition or condition group against context."""
        return condition.evaluate(context)

    def evaluate_switch(
        self,
        value: Any,
        cases: Dict[Any, str],
        default: Optional[str] = None,
    ) -> Optional[str]:
        """
        SWITCH/CASE evaluation.

        Returns the case value that matches, or default.
        """
        return cases.get(value, default)

    def evaluate_match(
        self,
        value: Any,
        patterns: Dict[Any, str],
        default: Optional[str] = None,
    ) -> Optional[str]:
        """
        Pattern matching evaluation.

        Returns the first matching pattern's value, or default.
        """
        for pattern, result in patterns.items():
            if callable(pattern) and pattern(value):
                return result
            if pattern == value:
                return result
        return default
