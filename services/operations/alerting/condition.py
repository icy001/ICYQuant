"""Condition engine (Commit 27 Part 1.3, spec section 8).

支持 6 种比较运算符；未知运算符抛 ValueError。
"""

from __future__ import annotations

from typing import Callable

Operator = Callable[[float, float], bool]


class ConditionEvaluator:

    OPERATORS: dict[str, Operator] = {
        ">": lambda value, threshold: value > threshold,
        ">=": lambda value, threshold: value >= threshold,
        "<": lambda value, threshold: value < threshold,
        "<=": lambda value, threshold: value <= threshold,
        "==": lambda value, threshold: value == threshold,
        "!=": lambda value, threshold: value != threshold,
    }

    def evaluate(
        self,
        value: float,
        operator: str,
        threshold: float,
    ) -> bool:

        if operator not in self.OPERATORS:
            raise ValueError(
                f"unsupported operator: {operator}"
            )

        return self.OPERATORS[operator](
            value,
            threshold,
        )
