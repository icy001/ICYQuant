"""
Cash repository.
"""


class CashRepository:
    def __init__(self):
        self.storage = {}

    def save(
        self,
        account,
    ):
        self.storage[account.currency] = account

    def get(
        self,
        currency,
    ):
        return self.storage.get(currency)