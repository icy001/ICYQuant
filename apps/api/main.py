"""ICYQuant API Gateway - Production entry point."""
from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.bootstrap import Bootstrap
from core.settings import get_settings
from shared.constants import APP_NAME, APP_VERSION

bootstrap = Bootstrap()

@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap.initialize()
    app.state.bootstrap = bootstrap
    yield
    bootstrap.shutdown()

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

@app.get("/")
async def root():
    return {
        "name": APP_NAME,
        "version": APP_VERSION,
        "docs": "/docs",
    }

@app.get("/health")
async def health():
    return bootstrap.health_checker.get_status()

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
    return bootstrap.get_status()