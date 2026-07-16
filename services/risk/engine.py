"""
Risk rule engine.
"""

from __future__ import annotations

from .context import RiskContext
from .decision import RiskResult
from .enums import RiskDecision


class RiskEngine:
    def __init__(
        self,
        rules,
    ):
        self.rules = list(rules)

    def evaluate(
        self,
        request,
        context: RiskContext,
    ) -> RiskResult:
        for rule in self.rules:
            result = rule.evaluate(request, context)
            if result is not None:
                return result
        return RiskResult(
            decision=RiskDecision.APPROVE
        )