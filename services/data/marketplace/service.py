"""
Dataset marketplace service.
"""


class MarketplaceService:
    def __init__(
        self,
        usage_tracker,
    ):
        self.usage_tracker = usage_tracker

    def subscribe(
        self,
        dataset,
    ):
        self.usage_tracker.record(dataset)