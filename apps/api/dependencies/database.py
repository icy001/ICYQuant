"""
FastAPI database dependencies.

Provides request scoped async sessions.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator


from sqlalchemy.ext.asyncio import (
    AsyncSession,
)


from services.database import (
    SessionFactory,
)


async def get_database_session(
) -> AsyncGenerator[AsyncSession, None]:
    """
    Provide one database session
    per request.
    """

    async with SessionFactory() as session:

        try:

            yield session

        finally:

            await session.close()