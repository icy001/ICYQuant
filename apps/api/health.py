"""
API health endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter

from services.database import (
    DatabaseHealth,
)

from services.database.session import (
    engine,
)


router = APIRouter()


database_health = DatabaseHealth(
    engine
)


@router.get(
    "/health/database"
)
async def database_health_check():

    return await database_health.check()