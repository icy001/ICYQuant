"""
Market gateway adapter protocol.
"""

from __future__ import annotations

from typing import Protocol, Any

from .quote import Quote


class MarketGatewayAdapter(Protocol):
    @property
    def provider(self) -> str:
        ...

    async def connect(self) -> None:
        ...

    async def disconnect(self) -> None:
        ...

    def normalize(
        self,
        payload: Any,
    ) -> Quote:
        ...