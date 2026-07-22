"""
Rule execution pipeline.
"""


class RulePipeline:

    def __init__(
        self,
        evaluator,
    ):

        self.evaluator = evaluator

    def execute(
        self,
        rules,
        context,
    ):

        return [
            self.evaluator.evaluate(
                rule,
                context,
            )
            for rule in rules
        ]