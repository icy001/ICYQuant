"""
Position application service.
"""

from __future__ import annotations

from decimal import Decimal

from ..engine import PositionEngine
from ..events import PositionUpdated
from ..model import Position
from ..publisher import PositionEventPublisher


class PositionService:
    def __init__(
        self,
        repository,
        publisher=None,
    ):
        self.repository = repository
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

        await self.repository.save(position)

        await self.publisher.publish(
            PositionUpdated(
                account_id=position.account_id,
                symbol=position.symbol,
                quantity=str(position.quantity),
            )
        )

        return position