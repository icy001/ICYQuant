"""
Market feed engine.
"""

from __future__ import annotations

from .metrics import FeedMetrics
from .validator import MarketDataValidator


class MarketFeedEngine:
    def __init__(
        self,
        repository,
        publisher,
    ):
        self.repository = repository
        self.publisher = publisher
        self.validator = MarketDataValidator()
        self.metrics = FeedMetrics()

    async def process(
        self,
        quote,
    ) -> bool:
        self.metrics.received += 1

        if not self.validator.validate(quote):
            self.metrics.rejected += 1
            return False

        await self.repository.save_quote(quote)
        await self.publisher.publish_quote(quote)

        self.metrics.published += 1

        return True