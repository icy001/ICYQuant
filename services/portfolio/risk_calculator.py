"""
Risk consumption calculator.
"""

from decimal import Decimal


class RiskCalculator:
    def calculate_remaining(
        self,
        budget,
    ):
        return budget.max_risk - budget.used_risk