"""
Database transaction manager.

Provides atomic transaction boundary.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
)


class TransactionManager:

    def __init__(
        self,
        session_factory,
    ):

        self.session_factory = session_factory

    @asynccontextmanager
    async def transaction(self):

        async with self.session_factory() as session:

            try:

                yield session

                await session.commit()

            except Exception:

                await session.rollback()

                raise

    async def commit(
        self,
        session: AsyncSession,
    ):

        await session.commit()

    async def rollback(
        self,
        session: AsyncSession,
    ):

        await session.rollback()