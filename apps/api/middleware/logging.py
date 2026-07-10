"""
HTTP request logging middleware.
"""

from __future__ import annotations

import time

from fastapi import Request

from starlette.middleware.base import (
    BaseHTTPMiddleware,
)

from services.observability import (
    create_logger,
)


logger = create_logger(
    "icyquant.api"
)


class LoggingMiddleware(
    BaseHTTPMiddleware
):
    async def dispatch(
        self,
        request: Request,
        call_next,
    ):
        start = time.time()
        response = await call_next(
            request
        )
        elapsed = (
            time.time()
            -
            start
        )
        logger.info(
            "http_request",
            extra={
                "context": {
                    "method":
                    request.method,
                    "path":
                    request.url.path,
                    "status":
                    response.status_code,
                    "latency_ms":
                    round(
                        elapsed * 1000,
                        2
                    )
                }
            }
        )
        return response