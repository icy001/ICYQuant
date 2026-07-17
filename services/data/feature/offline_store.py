"""
Historical feature storage.
"""


class OfflineFeatureStore:
    def __init__(self):
        self.storage = []

    async def save(
        self,
        feature,
    ):
        self.storage.append(feature)

    async def query(
        self,
        symbol,
    ):
        return [x for x in self.storage if x.symbol == symbol]