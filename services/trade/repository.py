"""
Trade repository.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database import Repository

from .model import Trade
from .orm import TradeModel
from .mapper import TradeMapper


class TradeRepository(
    Repository[TradeModel],
):
    def __init__(
        self,
        session: AsyncSession,
    ):
        super().__init__(
            session=session,
            model=TradeModel,
        )

    async def find_by_order_id(
        self,
        order_id: str,
    ) -> list[TradeModel]:
        result = await self.session.execute(
            select(TradeModel).where(
                TradeModel.order_id == order_id
            )
        )

        return list(result.scalars())

    async def find_by_execution_id(
        self,
        execution_id: str,
    ) -> TradeModel | None:
        result = await self.session.execute(
            select(TradeModel).where(
                TradeModel.execution_id == execution_id
            )
        )

        return result.scalar_one_or_none()

    async def save(
        self,
        trade: Trade,
    ):
        model = TradeMapper.to_model(trade)
        await self.create(model)
        return model

    async def get_trade(
        self,
        trade_id,
    ):
        model = await self.get(trade_id)
        return TradeMapper.to_domain(model)