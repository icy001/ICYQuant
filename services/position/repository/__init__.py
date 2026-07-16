"""
Position repository.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database import Repository

from ..exceptions import PositionNotFoundError
from ..mapper import PositionMapper
from ..model import Position
from ..orm import PositionModel


class PositionRepository(
    Repository[PositionModel],
):
    def __init__(
        self,
        session: AsyncSession,
    ):
        super().__init__(
            session=session,
            model=PositionModel,
        )

    async def find(
        self,
        account_id: str,
        symbol: str,
    ) -> Position | None:
        result = await self.session.execute(
            select(PositionModel).where(
                PositionModel.account_id == account_id,
                PositionModel.symbol == symbol,
            )
        )

        model = result.scalar_one_or_none()

        if model is None:
            return None

        return PositionMapper.to_domain(model)

    async def save(
        self,
        position: Position,
    ) -> None:
        existing = await self.session.execute(
            select(PositionModel).where(
                PositionModel.account_id == position.account_id,
                PositionModel.symbol == position.symbol,
            )
        )

        model = existing.scalar_one_or_none()

        if model is not None:
            model.quantity = position.quantity
            model.average_cost = position.average_cost
            model.realized_pnl = position.realized_pnl
            model.version = model.version + 1
            await self.session.flush()
        else:
            model = PositionMapper.to_model(position)
            await self.create(model)