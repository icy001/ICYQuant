"""
Market gateway orchestration.
"""

from __future__ import annotations

from .adapter import MarketGatewayAdapter


class MarketGateway:
    def __init__(
        self,
        adapter: MarketGatewayAdapter,
    ):
        self._adapter = adapter

    async def start(self) -> None:
        await self._adapter.connect()

    async def stop(self) -> None:
        await self._adapter.disconnect()

    def normalize(
        self,
        payload,
    ):
        return self._adapter.normalize(payload)