"""
Cash management engine.
"""

from decimal import Decimal


class CashManagementEngine:
    def deposit(
        self,
        account,
        amount: Decimal,
    ):
        account.balance += amount

    def withdraw(
        self,
        account,
        amount: Decimal,
    ):
        if self.available(account) < amount:
            raise ValueError("insufficient cash")

        account.balance -= amount

    def reserve(
        self,
        account,
        amount: Decimal,
    ):
        account.reserved += amount

    def available(
        self,
        account,
    ):
        return account.balance - account.reserved