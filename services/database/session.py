"""
Database session factory.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)


from .engine import (
    create_engine,
)


from .config import (
    load_database_settings,
)


settings = load_database_settings()


engine = create_engine(
    settings
)


SessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session():
    async with SessionFactory() as session:
        yield session