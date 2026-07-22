"""
Maintenance margin calculator.
"""


class MaintenanceMarginCalculator:

    def calculate(
        self,
        notional,
        ratio,
    ):

        return notional * ratio