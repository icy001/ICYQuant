"""
ICYQuant API Gateway.
"""

from fastapi import FastAPI

from apps.api.routers import (
    reconciliation,
)

from apps.api.middleware.tracing import (
    TraceMiddleware,
)

from apps.api.middleware.logging import (
    LoggingMiddleware,
)


app = FastAPI(
    title="ICYQuant API",
    version="0.3.0-beta2"
)


app.add_middleware(
    TraceMiddleware
)


app.add_middleware(
    LoggingMiddleware
)


app.include_router(
    reconciliation.router
)