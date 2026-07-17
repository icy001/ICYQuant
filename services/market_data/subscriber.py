"""
Market data subscriber protocol.
"""

from __future__ import annotations

from typing import Protocol

from .quote import Quote


class MarketSubscriber(Protocol):
    async def on_quote(
        self,
        quote: Quote,
    ) -> None:
        ...