"""
SQLAlchemy async engine.

Database connection layer.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    create_async_engine,
)


from .config import (
    DatabaseSettings,
)


def create_engine(
    settings: DatabaseSettings,
) -> AsyncEngine:
    return create_async_engine(
        settings.url,
        echo=settings.echo,
        pool_pre_ping=True,
    )