"""
Prometheus metrics endpoint.
"""

from __future__ import annotations

from fastapi import APIRouter

from fastapi.responses import Response

from services.observability.prometheus import (
    export_metrics,
)


router = APIRouter()


@router.get(
    "/metrics"
)
async def metrics():
    return Response(
        content=
        export_metrics(),
        media_type=
        "text/plain"
    )