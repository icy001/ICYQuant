"""
Alert rule evaluator.
"""


class RuleEvaluator:

    def evaluate(
        self,
        value,
        rule,
    ):
        return value > rule.threshold