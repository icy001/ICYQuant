"""
Portfolio limit checker.
"""

from decimal import Decimal


class LimitChecker:
    def check(
        self,
        asset,
        weight,
        rule,
    ):
        if weight > rule.max_weight:
            return True
        return False