"""
Cash manager.
"""


class CashManager:
    def debit(
        self,
        cash: float,
        amount: float,
    ) -> float:
        return cash - amount

    def credit(
        self,
        cash: float,
        amount: float,
    ) -> float:
        return cash + amount