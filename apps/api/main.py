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

from apps.api.middleware.otel import (
    OpenTelemetryMiddleware,
)

from apps.api.exception_handler import (
    global_exception_handler,
)

from apps.api.health import (
    router as health_router,
)

from apps.api.metrics import (
    router as metrics_router,
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


app.add_middleware(
    OpenTelemetryMiddleware
)


app.add_exception_handler(
    Exception,
    global_exception_handler
)


app.include_router(
    health_router
)


app.include_router(
    metrics_router
)


app.include_router(
    reconciliation.router
)