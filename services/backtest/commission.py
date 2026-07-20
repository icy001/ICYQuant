"""
Commission calculator.
"""


class CommissionCalculator:
    def calculate(
        self,
        quantity: float,
        price: float,
        rate: float = 0.0003,
    ):
        return quantity * price * rate