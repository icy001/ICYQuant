"""
Order repository.
"""

from __future__ import annotations

from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession

from services.database import Repository

from .enums import OrderStatus

from .orm import OrderModel


class OrderRepository(
    Repository[OrderModel],
):

    def __init__(
        self,
        session: AsyncSession,
    ):

        super().__init__(
            session=session,
            model=OrderModel,
        )

    async def find_by_status(
        self,
        status: OrderStatus,
    ) -> list[OrderModel]:

        result = await self.session.execute(
            select(OrderModel).where(
                OrderModel.status == status
            )
        )

        return list(
            result.scalars()
        )

    async def find_by_symbol(
        self,
        symbol: str,
    ) -> list[OrderModel]:

        result = await self.session.execute(
            select(OrderModel).where(
                OrderModel.symbol == symbol
            )
        )

        return list(
            result.scalars()
        )

    async def update_status(
        self,
        order: OrderModel,
        status: OrderStatus,
    ) -> None:

        order.status = status

        await self.session.flush()