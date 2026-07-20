"""
Capital allocation validation.
"""

from decimal import Decimal


class CapitalValidator:
    def validate(
        self,
        pool,
        amount: Decimal,
    ):
        return amount <= pool.available()