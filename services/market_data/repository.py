"""
Market data repository protocol.
"""

from __future__ import annotations

from typing import Protocol

from .quote import Quote


class MarketDataRepository(Protocol):
    async def save_quote(
        self,
        quote: Quote,
    ) -> None:
        ...

    async def get_quote(
        self,
        symbol: str,
    ) -> Quote | None:
        ...