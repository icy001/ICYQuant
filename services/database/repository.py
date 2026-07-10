"""
Generic repository implementation.

Provides database abstraction layer.
"""

from __future__ import annotations

from typing import (
    Generic,
    Type,
    TypeVar,
)

from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession

from .base import Base


ModelType = TypeVar(
    "ModelType",
    bound=Base,
)


class Repository(
    Generic[ModelType]
):

    def __init__(
        self,
        session: AsyncSession,
        model: Type[ModelType],
    ):

        self.session = session
        self.model = model

    async def create(
        self,
        obj: ModelType,
    ) -> ModelType:

        self.session.add(
            obj
        )

        await self.session.flush()

        return obj

    async def get(
        self,
        object_id,
    ) -> ModelType | None:

        result = await self.session.execute(
            select(
                self.model
            )
            .where(
                self.model.id
                ==
                object_id
            )
        )

        return result.scalar_one_or_none()

    async def list(
        self,
        limit: int = 100,
    ) -> list[ModelType]:

        result = await self.session.execute(
            select(
                self.model
            )
            .limit(
                limit
            )
        )

        return list(
            result.scalars()
        )

    async def delete(
        self,
        obj: ModelType,
    ):

        await self.session.delete(
            obj
        )

    async def count(
        self,
    ) -> int:

        result = await self.session.execute(
            select(
                self.model
            )
        )

        return len(
            result.scalars().all()
        )