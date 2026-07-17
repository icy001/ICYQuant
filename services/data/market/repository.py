"""
Market data repository.
"""


class MarketDataRepository:
    def __init__(self):
        self.storage = []

    async def save(
        self,
        data,
    ):
        self.storage.append(data)

    async def query(
        self,
    ):
        return self.storage