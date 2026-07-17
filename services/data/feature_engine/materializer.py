"""
Feature materialization.
"""


class FeatureMaterializer:
    def __init__(
        self,
        store,
    ):
        self.store = store

    async def write(
        self,
        features,
    ):
        for feature in features:
            await self.store.save(feature)