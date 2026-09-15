"""
Market feed engine.
"""

from __future__ import annotations

from dataclasses import dataclass

from .validator import MarketDataValidator


@dataclass
class FeedMetrics:
    # Restored from the original metrics module: the Commit 16 rewrite
    # repurposed services/market_data/metrics.py for Prometheus, so this
    # three-field counter lives with its only consumer now.
    received: int = 0
    published: int = 0
    rejected: int = 0


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