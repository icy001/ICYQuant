"""
API health endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter

from services.observability.health import (
    healthy,
)


router = APIRouter()


@router.get(
    "/health"
)
async def health_check():
    result = healthy(
        "icyquant-api"
    )
    return {
        "service":
        result.service,
        "status":
        result.status.value,
        "message":
        result.message,
    }