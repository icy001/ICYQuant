"""
Position application service.
"""

from __future__ import annotations

from decimal import Decimal

from ..engine import PositionEngine
from ..events import create_position_updated
from ..model import Position
from ..publisher import PositionEventPublisher


class PositionService:
    def __init__(
        self,
        repository,
        trade_repository,
        publisher=None,
    ):
        self.repository = repository
        self.trade_repository = trade_repository
        self.engine = PositionEngine()
        self.publisher = (
            publisher
            or PositionEventPublisher()
        )

    async def apply_trade(
        self,
        trade,
    ):
        position = await self.repository.find(
            trade.account_id,
            trade.symbol,
        )

        if position is None:
            position = Position(
                account_id=trade.account_id,
                symbol=trade.symbol,
            )

        self.engine.apply_trade(
            position,
            trade.quantity,
            trade.price,
        )

        await self.repository.upsert(position)

        await self.publisher.publish(
            create_position_updated(
                account_id=position.account_id,
                symbol=position.symbol,
                quantity=str(position.quantity),
                version=position.version,
            )
        )

        return position

    async def apply_trade_by_id(
        self,
        trade_id,
    ):
        trade = await self.trade_repository.get_trade(
            trade_id
        )
        return await self.apply_trade(trade)