"""
Journal repository.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from services.database import Repository

from ..journal import Journal
from ..mapper import JournalMapper
from ..orm import JournalModel


class JournalRepository(
    Repository[JournalModel],
):
    def __init__(
        self,
        session: AsyncSession,
    ):
        super().__init__(
            session=session,
            model=JournalModel,
        )

    async def save(
        self,
        journal: Journal,
    ):
        model = JournalMapper.to_model(
            journal
        )

        await self.create(
            model
        )

        return model