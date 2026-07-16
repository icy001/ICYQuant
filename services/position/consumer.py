"""
Trade event consumer.
"""

from __future__ import annotations

from services.trade import TradeCreated


class PositionConsumer:
    def __init__(
        self,
        service,
    ) -> None:
        self.service = service

    async def handle(
        self,
        event: TradeCreated,
    ) -> None:
        await self.service.apply_trade_by_id(
            event.trade_id
        )