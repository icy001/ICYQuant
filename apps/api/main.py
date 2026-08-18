"""ICYQuant API Gateway - Production entry point."""
from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.bootstrap import BootstrapManager, get_bootstrap
from core.settings import get_settings
from shared.constants import APP_NAME, APP_VERSION

bootstrap: BootstrapManager = get_bootstrap()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await bootstrap.startup()
    app.state.bootstrap = bootstrap
    yield
    await bootstrap.shutdown()

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from apps.api.metrics import router as metrics_router  # noqa: E402
from apps.api.routers import router as ping_router  # noqa: E402
from apps.api.routers.reconciliation import router as reconciliation_router  # noqa: E402
from apps.api.health import router as health_router  # noqa: E402

app.include_router(metrics_router)
app.include_router(ping_router)
app.include_router(health_router)
app.include_router(reconciliation_router)

@app.get("/")
async def root():
    return {
        "name": APP_NAME,
        "version": APP_VERSION,
        "docs": "/docs",
    }

@app.get("/health")
async def health():
    """Aggregated health of all 10 logical services (real checks)."""
    from apps.runtime.health_server import build_registry

    registry = build_registry()
    snapshot = registry.snapshot()
    snapshot["bootstrap"] = bootstrap.report()
    return snapshot

@app.get("/ready")
async def ready():
    return {"ready": bootstrap.is_ready()}

@app.get("/version")
async def version():
    settings = get_settings()
    return {
        "version": settings.APP_VERSION,
        "env": settings.APP_ENV,
        "status": "stable" if bootstrap.is_ready() else "starting",
    }

@app.get("/status")
async def status():
    return bootstrap.report()
