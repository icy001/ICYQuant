"""
Ledger trade consumer.
"""

from __future__ import annotations

from services.trade import TradeCreated


class LedgerConsumer:
    def __init__(
        self,
        service,
    ) -> None:
        self.service = service

    async def handle(
        self,
        event: TradeCreated,
    ) -> None:
        await self.service.post_trade_by_id(
            event.trade_id
        )