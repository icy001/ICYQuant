"""
Position repository.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database import Repository

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
        model = PositionMapper.to_model(position)
        await self.create(model)