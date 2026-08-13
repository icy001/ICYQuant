"""Runbook condition (Commit 27 Part 1.5).

条件用于把 Runbook Step 与可观测信号（Metric / Service State）绑定：

    RunbookStep
        ↓
    RunbookCondition(metric, operator, threshold)
        ↓
    evaluate_condition(condition, value)
        ↓
    True / False
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ConditionOperator(str, Enum):

    GT = "gt"

    GTE = "gte"

    LT = "lt"

    LTE = "lte"

    EQ = "eq"

    NE = "ne"


_OPERATORS = {
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


@dataclass(frozen=True)
class RunbookCondition:

    condition_id: str

    description: str

    metric: str | None = None

    operator: ConditionOperator | str | None = None

    threshold: float | None = None

    expected: str | None = None


def evaluate_condition(
    condition: RunbookCondition,
    value,
) -> bool:
    """确定性求值。

    - expected 提供时进行字符串相等比较；
    - 否则必须提供 operator + threshold。
    """

    if condition.expected is not None:
        return str(value) == condition.expected

    if condition.operator is None or condition.threshold is None:
        raise ValueError(
            f"condition {condition.condition_id} requires "
            f"operator and threshold (or expected)"
        )

    operator = getattr(
        condition.operator,
        "value",
        condition.operator,
    )

    fn = _OPERATORS.get(operator)

    if fn is None:
        raise ValueError(
            f"unsupported operator: {condition.operator}"
        )

    return fn(value, condition.threshold)
