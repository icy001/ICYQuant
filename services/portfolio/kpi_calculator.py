"""
KPI calculator.
"""

from decimal import Decimal


class KPICalculator:
    def calculate_return(
        self,
        start,
        end,
    ):
        if start == 0:
            return Decimal("0")
        return (end - start) / start