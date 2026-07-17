"""
In-memory market cache.
"""

from __future__ import annotations

from .quote import Quote


class InMemoryMarketCache:
    def __init__(self):
        self._quotes: dict[str, Quote] = {}

    async def save_quote(
        self,
        quote: Quote,
    ) -> None:
        self._quotes[quote.symbol] = quote

    async def get_quote(
        self,
        symbol: str,
    ) -> Quote | None:
        return self._quotes.get(symbol)