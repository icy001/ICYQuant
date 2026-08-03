"""
Database session manager.

Provides async session lifecycle management,
transaction handling, Unit of Work pattern,
and base repository implementation.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from .engine import DatabaseEngine
from .exceptions import (
    DatabaseConnectionError,
    DatabaseTransactionError,
)


class DatabaseSession:
    """
    Async session manager.

    Provides context managers for session
    and transaction lifecycle management.
    All database access must go through this
    class to ensure consistency.
    """

    def __init__(
        self,
        engine: DatabaseEngine,
    ) -> None:

        self._engine = engine

    @asynccontextmanager
    async def session(
        self,
    ) -> AsyncIterator[AsyncSession]:
        """
        Create an async session with auto-close.

        Yields a session that is automatically
        closed after use. Rollbacks on error.
        """

        async with (
            self._engine
            .session_factory()
        ) as session:

            try:

                yield session

            except Exception:

                await session.rollback()

                raise

            finally:

                await session.close()

    @asynccontextmanager
    async def transaction(
        self,
    ) -> AsyncIterator[AsyncSession]:
        """
        Create an async session with transaction.

        Yields a session with automatic commit
        on success and rollback on failure.
        """

        async with self.session() as session:

            try:

                yield session

                await session.commit()

            except Exception as exc:

                await session.rollback()

                raise DatabaseTransactionError(
                    str(exc)
                ) from exc


class UnitOfWork:
    """
    Unit of Work.

    Encapsulates a transactional boundary
    for business operations. All repository
    operations within a UoW share the same
    transaction.
    """

    def __init__(
        self,
        sessions: DatabaseSession,
    ) -> None:

        self._sessions = sessions

    @asynccontextmanager
    async def start(
        self,
    ) -> AsyncIterator[AsyncSession]:
        """
        Start a new unit of work.

        Opens a transaction and yields the
        session for repository operations.
        """

        async with (
            self._sessions.transaction()
        ) as session:

            yield session


class Repository:
    """
    Base repository.

    Provides a session reference for
    derived repository classes to perform
    database operations.
    """

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:

        self.session = session