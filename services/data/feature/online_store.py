"""
Realtime feature storage.
"""


class OnlineFeatureStore:
    def __init__(self):
        self.cache = {}

    async def put(
        self,
        feature,
    ):
        key = (feature.symbol, feature.name)
        self.cache[key] = feature

    async def get(
        self,
        symbol,
        name,
    ):
        return self.cache.get((symbol, name))