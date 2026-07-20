"""
Position limit checker.
"""


class PositionLimitChecker:
    def check(
        self,
        quantity,
        rule,
    ):
        return quantity <= rule.max_position