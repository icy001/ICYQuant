"""
Market publisher.
"""

from __future__ import annotations

from .quote import Quote
from .subscription_manager import SubscriptionManager


class MarketPublisher:
    def __init__(
        self,
        manager: SubscriptionManager,
    ):
        self.manager = manager

    async def publish_quote(
        self,
        quote: Quote,
    ) -> None:
        await self.manager.publish(quote)