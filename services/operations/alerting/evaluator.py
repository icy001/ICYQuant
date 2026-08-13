"""Alert rule evaluator (Commit 27 Part 1.3, spec sections 12, 31).

先检查 rule.enabled，再评估条件。
"""

from __future__ import annotations

from .condition import ConditionEvaluator
from .rule import AlertRule


class AlertRuleEvaluator:

    def __init__(
        self,
        condition_evaluator: ConditionEvaluator,
    ) -> None:

        self.condition = condition_evaluator

    def evaluate(
        self,
        rule: AlertRule,
        value: float,
    ) -> bool:

        if not rule.enabled:
            return False

        return self.condition.evaluate(
            value,
            rule.operator,
            rule.threshold,
        )
