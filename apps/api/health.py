"""
API health endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter

from services.database import (
    DatabaseHealth,
    create_engine,
    load_database_settings,
)


router = APIRouter()


engine = create_engine(
    load_database_settings()
)


database_health = DatabaseHealth(
    engine
)


@router.get(
    "/health/database"
)
async def database_health_check():

    return await database_health.check()