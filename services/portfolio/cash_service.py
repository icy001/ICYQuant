"""
Cash service.
"""


class CashService:
    def __init__(
        self,
        engine,
        repository,
    ):
        self.engine = engine
        self.repository = repository

    def deposit(
        self,
        currency,
        amount,
    ):
        account = self.repository.get(currency)
        self.engine.deposit(account, amount)
        return account