"""
Cash ledger.
"""


class CashLedger:

    def __init__(
        self,
        initial_cash,
    ):

        self.cash = initial_cash


    def deposit(
        self,
        amount,
    ):

        self.cash += amount


    def withdraw(
        self,
        amount,
    ):

        self.cash -= amount


    def balance(self):

        return self.cash