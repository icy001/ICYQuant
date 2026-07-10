"""
Database session factory.
"""

from __future__ import annotations

from typing import (
    Optional,
)

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)


from .engine import (
    create_engine,
)


from .config import (
    load_database_settings,
)


_settings = load_database_settings()

_engine: Optional[AsyncEngine] = None

SessionFactory: Optional[async_sessionmaker[AsyncSession]] = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_engine(
            _settings
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global SessionFactory
    if SessionFactory is None:
        SessionFactory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return SessionFactory


async def get_session():
    async with get_session_factory()() as session:
        yield session