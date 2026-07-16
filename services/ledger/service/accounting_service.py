"""
Accounting application service.
"""

from __future__ import annotations

from ..events import LedgerPosted
from ..posting import PostingEngine
from ..publisher import (
    LedgerEventPublisher,
)


class AccountingService:
    def __init__(
        self,
        repository,
        trade_repository,
        publisher=None,
    ):
        self.repository = repository
        self.trade_repository = trade_repository
        self.posting = PostingEngine()
        self.publisher = (
            publisher
            or
            LedgerEventPublisher()
        )

    async def post_trade(
        self,
        trade,
    ):
        journal = self.posting.post_trade(
            trade
        )

        await self.repository.save(
            journal
        )

        await self.publisher.publish(
            LedgerPosted(
                journal_id=journal.journal_id,
            )
        )

        return journal

    async def post_trade_by_id(
        self,
        trade_id,
    ):
        trade = await self.trade_repository.get_trade(
            trade_id
        )

        return await self.post_trade(
            trade
        )