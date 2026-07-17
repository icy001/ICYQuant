"""
Factor expression engine.
"""


class FactorExpressionEngine:
    def evaluate(
        self,
        expression,
        context,
    ):
        return eval(expression, {}, context)