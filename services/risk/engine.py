from typing import List

from .rules import RiskRule
from .context import RiskContext
from .result import RiskResult, RiskDecision


class RiskEngine:
    def __init__(self, rules: List[RiskRule] = None):
        self.rules = rules or []

    def evaluate(self, order, context: RiskContext) -> RiskResult:
        current_order = order

        for rule in self.rules:
            result = rule.evaluate(current_order, context)

            if result.decision == RiskDecision.MODIFY and result.modified_order:
                current_order = result.modified_order

            if result.decision != RiskDecision.PASS:
                return result

        return RiskResult(
            decision=RiskDecision.PASS,
            message="All risk rules passed"
        )

    def evaluate_all(self, orders: List, context: RiskContext) -> List[RiskResult]:
        return [self.evaluate(order, context) for order in orders]