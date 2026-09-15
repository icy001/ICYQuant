"""ICYQuant API Gateway - Production entry point."""
from __future__ import annotations
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.bootstrap import BootstrapManager, get_bootstrap
from core.settings import get_settings
from shared.constants import APP_NAME, APP_VERSION

bootstrap: BootstrapManager = get_bootstrap()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Seed Dashboard users / roles and register service health checks.
    from apps.dashboard.auth import auth as dashboard_auth
    from apps.dashboard import runtime as dashboard_runtime
    from apps.runtime.health_server import build_registry

    dashboard_auth.seed()
    registry = build_registry()
    for name, service in registry.services.items():
        dashboard_runtime.register_health(name, service.check)

    # Seed the Multi-Account Adapter Layer (4 market adapters + accounts).
    from apps.adapters.service import service as adapter_service

    adapter_service.ensure_seeded()

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
from apps.api.routers.accounts import (  # noqa: E402
    accounts_error_handler,
    router as accounts_router,
)
from apps.api.routers.market_data import (  # noqa: E402
    market_data_error_handler,
    router as market_data_router,
)
from apps.api.routers.reconciliation import router as reconciliation_router  # noqa: E402
from apps.api.health import router as health_router  # noqa: E402
from apps.dashboard import dashboard_router  # noqa: E402
from services.account.domain.exceptions import AccountError  # noqa: E402
from services.market_data.market_data_service import (  # noqa: E402
    MarketDataServiceError,
)

# Commit 010 §13 — one typed error envelope for the whole Market Data
# API (400 invalid parameter / 404 unknown symbol / 503 unavailable).
app.add_exception_handler(MarketDataServiceError, market_data_error_handler)

# Commit 015 §15 — same contract for Account / Position Sync.  A domain
# AccountError falls back to 400; sync errors carry their own status.
app.add_exception_handler(AccountError, accounts_error_handler)

app.include_router(metrics_router)
app.include_router(ping_router)
app.include_router(health_router)
app.include_router(reconciliation_router)
app.include_router(market_data_router)
app.include_router(accounts_router)
app.include_router(dashboard_router)

@app.get("/")
async def root():
    return {
        "name": APP_NAME,
        "version": APP_VERSION,
        "docs": "/docs",
        "dashboard": "/dashboard/",
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

# Serve the Trading Dashboard SPA (zero-dependency static bundle).
_DASHBOARD_STATIC = Path(__file__).resolve().parent.parent / "dashboard" / "static"
app.mount(
    "/dashboard",
    StaticFiles(directory=str(_DASHBOARD_STATIC), html=True),
    name="dashboard",
)
