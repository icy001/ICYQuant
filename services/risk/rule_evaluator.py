"""
Rule evaluator.
"""


class RuleEvaluator:

    def evaluate(
        self,
        rule,
        context,
    ):

        if not rule.enabled:

            return False

        return True