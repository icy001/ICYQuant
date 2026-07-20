"""
Market data provider.
"""


class MarketDataProvider:
    def __init__(
        self,
        dataset_service,
    ):
        self.dataset_service = dataset_service

    async def load(
        self,
        dataset,
    ):
        return await self.dataset_service.load(dataset)