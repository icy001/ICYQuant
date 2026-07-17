"""
Subscription manager.
"""

from __future__ import annotations

from collections import defaultdict

from .quote import Quote


class SubscriptionManager:
    def __init__(self):
        self._subscribers = defaultdict(list)

    def subscribe(
        self,
        symbol: str,
        subscriber,
    ) -> None:
        self._subscribers[symbol].append(subscriber)

    def unsubscribe(
        self,
        symbol: str,
        subscriber,
    ) -> None:
        self._subscribers[symbol].remove(subscriber)

    async def publish(
        self,
        quote: Quote,
    ) -> None:
        for subscriber in self._subscribers.get(quote.symbol, []):
            await subscriber.on_quote(quote)