"""Global exception handlers."""
from __future__ import annotations
import logging
from fastapi import Request
from fastapi.responses import JSONResponse

from shared.exceptions import (
    ICYQuantError,
    ValidationError,
    NotFoundError,
    AuthenticationError,
    AuthorizationError,
    InfrastructureError,
)

logger = logging.getLogger(__name__)

async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error_code": 1000,
        },
    )

async def icyquant_exception_handler(request: Request, exc: ICYQuantError):
    status_map = {
        ValidationError: 400,
        AuthenticationError: 401,
        AuthorizationError: 403,
        NotFoundError: 404,
        InfrastructureError: 503,
    }
    status_code = status_map.get(type(exc), 500)
    return JSONResponse(
        status_code=status_code,
        content={
            "detail": exc.message,
            "error_code": exc.error_code,
        },
    )

def register_exception_handlers(app) -> None:
    app.add_exception_handler(Exception, global_exception_handler)
    app.add_exception_handler(ICYQuantError, icyquant_exception_handler)