"""
Database connection manager.
"""

from __future__ import annotations

from sqlalchemy import (
    create_engine,
)

from sqlalchemy.orm import (
    sessionmaker,
)


DATABASE_URL = (
    "postgresql+psycopg://"
    "icyquant:password@"
    "postgres:5432/icyquant"
)


engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)