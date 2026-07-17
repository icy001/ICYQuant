"""
Feed pipeline.
"""

from __future__ import annotations

from .feed import MarketFeedEngine


class MarketPipeline:
    def __init__(
        self,
        feed: MarketFeedEngine,
    ):
        self.feed = feed

    async def on_quote(
        self,
        quote,
    ) -> bool:
        return await self.feed.process(quote)